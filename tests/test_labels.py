import unittest

import pandas as pd

from src.labels import add_label_columns, attack_family, normalize_label


class LabelTests(unittest.TestCase):
    def test_normalization_preserves_class_identity(self):
        self.assertEqual(normalize_label(" Web   Attack - XSS "), "Web Attack - XSS")

    def test_derived_labels_do_not_overwrite_raw_label(self):
        frame = pd.DataFrame({"Label": ["BENIGN", "Botnet - Attempted"]})
        result = add_label_columns(frame)
        self.assertEqual(result["Label"].tolist(), ["BENIGN", "Botnet - Attempted"])
        self.assertEqual(result["binary_label"].tolist(), [0, 1])
        self.assertEqual(result["is_attempted"].tolist(), [0, 1])
        self.assertEqual(result["attack_family"].tolist(), ["BENIGN", "BOTNET"])

    def test_family_mapping_is_explicit(self):
        self.assertEqual(attack_family("DoS Hulk - Attempted"), "DOS")
        self.assertEqual(attack_family("Infiltration - Portscan"), "PORT_SCAN")


if __name__ == "__main__":
    unittest.main()
