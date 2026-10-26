"""Nested OOF cho scalar P_attack, không nối latent khác hệ tọa độ vào Stage 2.

Mỗi outer fold: scaler/AE/classifier fit inner-fit; AE/classifier early-stop inner-stop;
Platt fit inner-calibration; outer-holdout chỉ transform/predict. Các scope đều là train
Phase 2 và đã loại heldout LOACO. Chi phí cao hơn legacy (5 AE nếu representation=latent).
Final model dùng representation chung và toàn known train, val cho early stopping;
final calibrator fit RAW OOF train, chỉ áp lên final validation/test, KHÔNG áp lại OOF.
"""
from __future__ import annotations

import gc
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from src.artifact_contracts import read_contract, require_link, sidecar, write_contract
from src.calibration import apply_platt_calibrator, fit_platt_calibrator, save_calibrator
from src.contracts import assert_new_outputs, probability_vector
from src.metrics import binary_metrics
from src.model_config import experiment_id, load_model_config, phase_directory, project_path
from src.model_data import load_prepared_arrays, split_indices, validate_held_out_label
from src.research_protocol import fit_transform_scope, inner_partitions, require_preprocessing
from src.training_utils import save_json


def _fit_predict(kind, config, features, targets, fit, stop, groups, checkpoint, seed, device):
    from src.runtime import set_reproducible_seed
    set_reproducible_seed(seed)
    if kind == 'xgboost':
        from src.stage1_xgboost import fit_classifier, positive_probability, save_classifier
        model = fit_classifier(features[fit], targets[fit], features[stop], targets[stop], config['stage1']['xgboost'], seed)
        save_classifier(model, checkpoint.with_suffix('.json'))
        predictions = {name: np.concatenate([positive_probability(model, features[ids[i:i + 65536]]) for i in range(0, len(ids), 65536)]) for name, ids in groups.items()}
    else:
        from src.stage1_mlp import train_binary_mlp, predict_binary_mlp
        model, history = train_binary_mlp(features, targets, fit, stop, config['stage1']['mlp'], config['hardware'], device, checkpoint.with_suffix('.pt'), seed)
        save_json(checkpoint.with_name(checkpoint.name + '_history.json'), history.to_dict())
        predictions = {name: predict_binary_mlp(model, features, ids, int(config['stage1']['mlp']['batch_size']), device, config['hardware']) for name, ids in groups.items()}
    del model
    return predictions


def run_stage1(args):
    from src.console import configure_utf8_console
    configure_utf8_console()
    config = load_model_config(args.config)
    run_id = experiment_id(config, args.run_id)
    seed = int(config['experiment']['random_state'])
    processed = project_path(config, config['experiment']['processed_dir'])
    arrays, scaled_path, _ = require_preprocessing(config, run_id, args.held_out_label_id)
    feature_path = scaled_path
    if args.representation == 'latent':
        feature_path = Path(args.latent_path).resolve() if args.latent_path else processed / 'experiments' / run_id / 'latent_features.npy'
        latent_record = read_contract(feature_path, config, args.held_out_label_id, kind='latent', run_id=run_id)
        require_link(latent_record, scaled_path)
        arrays = load_prepared_arrays(processed, feature_path)
    validate_held_out_label(arrays.attack_label_ids, args.held_out_label_id)
    train = split_indices(arrays.split_ids, 0, args.held_out_label_id, arrays.attack_label_ids)
    validation = split_indices(arrays.split_ids, 1, args.held_out_label_id, arrays.attack_label_ids)
    test = split_indices(arrays.split_ids, 2)
    tag = f'{args.model}_{args.representation}'
    model_dir = phase_directory(config, 'models_dir', 'stage1', run_id) / tag
    result_dir = phase_directory(config, 'results_dir', 'stage1', run_id) / tag
    metadata = phase_directory(config, 'metadata_dir', 'stage1', run_id) / f'{tag}.json'
    output = processed / 'experiments' / run_id / f'stage1_{tag}_p_attack_all.npy'
    assert_new_outputs(model_dir, result_dir, metadata, output)
    from sklearn.model_selection import StratifiedKFold
    splitter = StratifiedKFold(n_splits=int(config['stage1']['oof_folds']), shuffle=True, random_state=seed)
    partitions = []
    for fold, (fit_positions, holdout_positions) in enumerate(splitter.split(np.zeros(len(train)), arrays.binary_labels[train]), 1):
        fit, stop, calibration = inner_partitions(train[fit_positions], arrays.binary_labels, seed + fold)
        partitions.append((fit, stop, calibration, train[holdout_positions], holdout_positions))
    plan = {'protocol': args.protocol, 'run_id': run_id, 'model': args.model, 'representation': args.representation,
            'feature_path': str(feature_path), 'feature_shape': list(arrays.features.shape),
            'held_out_label_id': args.held_out_label_id, 'train_samples': len(train), 'validation_samples': len(validation),
            'test_samples': len(test), 'oof_folds': len(partitions), 'inner_fractions': [0.8, 0.1, 0.1],
            'p_attack_contract': 'outer holdout excluded from scaler/AE/classifier fit, stopping and fold calibration',
            'final_calibration': 'raw outer OOF train; applied only to final validation/test',
            'stage2_representation': 'one common encoder; fold-specific coordinates never concatenated',
            'test_used_for_training_calibration_or_selection': False, 'probabilities_path': str(output),
            'status': 'checked_only' if args.check_only else 'running'}
    print(plan)
    if args.check_only:
        print('CHECK-ONLY OK: đã kiểm contract và nested partitions; không fit model')
        return
    from src.runtime import clear_cuda_cache, configure_torch_runtime, set_reproducible_seed
    device = configure_torch_runtime(config['hardware']) if args.model == 'mlp' or args.representation == 'latent' else None
    save_json(metadata, plan)
    raw = np.load(processed / 'features_raw.npy', mmap_mode='r', allow_pickle=False)
    raw_oof = np.empty(len(train), dtype=np.float32)
    calibrated_oof = np.empty(len(train), dtype=np.float32)
    use_calibration = config['stage1'].get('calibrate_probabilities', True)
    for fold, (fit, stop, calibration, holdout, positions) in enumerate(partitions, 1):
        fold_dir = model_dir / f'fold_{fold}'
        fold_dir.mkdir(parents=True)
        for name, ids in [('fit', fit), ('stop', stop), ('calibration', calibration), ('holdout', holdout)]:
            np.save(fold_dir / f'{name}_indices.npy', ids)
        print(f'[nested OOF {fold}] fit={len(fit)}, stop={len(stop)}, calibration={len(calibration)}, predict={len(holdout)}')
        # Cache mới do chính run tạo, xóa tự động sau fold; scaler/model/indices được giữ lại.
        with TemporaryDirectory(prefix='feature_cache_', dir=fold_dir) as temporary:
            cache = Path(temporary)
            scaled = fit_transform_scope(raw, fit, cache / 'scaled.npy', fold_dir / 'scaler.joblib')
            features = scaled
            try:
                if args.representation == 'latent':
                    from src.autoencoder import train_autoencoder, encode_to_memmap
                    set_reproducible_seed(seed + fold)
                    encoder, history, _, _ = train_autoencoder(scaled, fit, stop, config['autoencoder'], config['hardware'], device, fold_dir / 'encoder.pt', random_state=seed + fold)
                    save_json(fold_dir / 'encoder_history.json', history.to_dict())
                    encode_to_memmap(encoder, scaled, cache / 'latent.npy', int(config['autoencoder']['latent_dim']), int(config['autoencoder']['encode_batch_size']), device, config['hardware'])
                    del encoder
                    clear_cuda_cache()
                    features = np.load(cache / 'latent.npy', mmap_mode='r', allow_pickle=False)
                scores = _fit_predict(args.model, config, features, arrays.binary_labels, fit, stop,
                                      {'holdout': holdout, 'calibration': calibration}, fold_dir / 'classifier', seed + fold, device)
                raw_oof[positions] = scores['holdout']
                if use_calibration:
                    calibrator = fit_platt_calibrator(scores['calibration'], arrays.binary_labels[calibration], seed + fold)
                    save_calibrator(calibrator, fold_dir / 'platt.joblib')
                    calibrated_oof[positions] = apply_platt_calibrator(calibrator, scores['holdout'])
                else:
                    calibrated_oof[positions] = scores['holdout']
            finally:
                if features is not scaled:
                    features._mmap.close()
                scaled._mmap.close()
        gc.collect()
        clear_cuda_cache()
    # Calibrator cuối không tái áp lên OOF. OOF đã có calibrator riêng, độc lập target hàng đó.
    final_calibrator = fit_platt_calibrator(raw_oof, arrays.binary_labels[train], seed) if use_calibration else None
    if final_calibrator is not None:
        save_calibrator(final_calibrator, model_dir / 'platt_calibrator.joblib')
    final = _fit_predict(args.model, config, arrays.features, arrays.binary_labels, train, validation,
                         {'validation': validation, 'test': test}, model_dir / 'final', seed, device)
    before_calibration = {name: binary_metrics(arrays.binary_labels[ids], final[name]) for name, ids in [('validation', validation), ('test', test)]}
    if final_calibrator is not None:
        final = {name: apply_platt_calibrator(final_calibrator, scores) for name, scores in final.items()}
    all_probabilities = np.full(len(raw), np.nan, dtype=np.float32)
    for ids, scores in [(train, calibrated_oof), (validation, final['validation']), (test, final['test'])]:
        probability_vector(scores, length=len(ids))
        all_probabilities[ids] = scores
    np.save(output, all_probabilities)
    result_dir.mkdir(parents=True)
    np.save(result_dir / 'oof_train_indices.npy', train)
    np.save(result_dir / 'raw_oof.npy', raw_oof)
    report = {**plan, 'status': 'completed', 'raw_oof_metrics': binary_metrics(arrays.binary_labels[train], raw_oof),
              'oof_train_metrics': binary_metrics(arrays.binary_labels[train], calibrated_oof),
              'before_calibration_metrics': before_calibration,
              'validation_metrics': binary_metrics(arrays.binary_labels[validation], final['validation']),
              'test_metrics': binary_metrics(arrays.binary_labels[test], final['test'])}
    save_json(metadata, report)
    save_json(result_dir / 'metrics.json', report)
    parents = [feature_path, sidecar(feature_path), metadata, *sorted(p for p in model_dir.rglob('*') if p.is_file())]
    write_contract(output, config, run_id, args.held_out_label_id, 'p_attack', parents=parents, extra=plan)
    arrays.close()
    raw._mmap.close()
    print(f'Đã lưu nested OOF/final P_attack: {output}')
