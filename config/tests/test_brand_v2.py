from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2] / 'assets/images/brand/v2'
NS = '{http://www.w3.org/2000/svg}'

class BrandV2AssetTests(unittest.TestCase):
    def test_assets(self):
        names = {'symbol','symbol-light','symbol-dark','symbol-monochrome','ai-avatar','favicon-compact','wordmark','horizontal','vertical','orbit-artwork','knowledge-artwork'}
        self.assertEqual({p.stem for p in ROOT.glob('*.svg')}, names)
    def test_safe_vectors_and_budgets(self):
        allowed = {'svg','path','g','circle','ellipse'}
        attrs = {'viewBox','d','fill','fill-rule','transform','cx','cy','r','rx','ry','stroke','stroke-width'}
        for p in ROOT.glob('*.svg'):
            with self.subTest(asset=p.name):
                raw = p.read_bytes()
                self.assertNotIn(b'<!', raw)
                self.assertLessEqual(len(raw), 2048 if p.stem=='favicon-compact' else 8192 if p.stem=='wordmark' else 12288 if 'artwork' in p.stem else 4096)
                tree = ET.fromstring(raw)
                self.assertEqual(tree.tag, NS+'svg')
                self.assertIn('viewBox', tree.attrib)
                for node in tree.iter():
                    self.assertTrue(node.tag.startswith(NS))
                    self.assertIn(node.tag[len(NS):], allowed)
                    self.assertLessEqual(set(node.attrib), attrs)
                    for value in node.attrib.values():
                        self.assertNotIn('url(', value.lower())
    def test_canonical_geometry(self):
        paths = [ET.parse(ROOT / n).getroot()[0].attrib['d'] for n in ('symbol.svg','symbol-light.svg','symbol-dark.svg','symbol-monochrome.svg','ai-avatar.svg')]
        self.assertEqual(len(set(paths)), 1)
        self.assertNotEqual(paths[0], ET.parse(ROOT/'favicon-compact.svg').getroot()[0].attrib['d'])
