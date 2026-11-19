"""Annotation export gates and display transforms; no microscope connection."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import numpy as np
    import nd2
    from PIL import Image
    spec=importlib.util.spec_from_file_location("prepare_annotation",
        Path(__file__).resolve().parents[1]/"scripts/prepare_spot_annotation.py")
    builder=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    HAVE_DEPS=True
except ImportError:
    HAVE_DEPS=False


@unittest.skipUnless(HAVE_DEPS,"needs optional annotation dependencies")
class PrepareAnnotationTests(unittest.TestCase):
    def fixture(self,root,expected=None):
        source=root/builder.EXPECTED_NAME
        source.write_bytes(b"raw")
        digest=expected or hashlib.sha256(b"raw").hexdigest()
        manifest=root/"baseline.csv"
        manifest.write_text("file_name,size_bytes,raw_sha256\n"+source.name+",3,"+digest+"\n")
        template=root/"template.html"
        template.write_text("<script>const manifest=__ANNOTATION_MANIFEST__;</script>")
        return source,manifest,template

    def test_display_transform_preserves_geometry_and_source_pixels(self):
        plane=np.array([[0,10,20],[20,10,0]],dtype=np.uint16)
        original=plane.copy()
        result=builder.display_plane(plane,0,20)
        self.assertEqual(result.size,(3,2))
        self.assertEqual(np.asarray(result).tolist(),[[0,128,255],[255,128,0]])
        np.testing.assert_array_equal(plane,original)
        later=builder.display_plane(plane//2,0,20)
        self.assertEqual(np.asarray(later)[0,2],128)

    def test_invalid_display_range_is_rejected(self):
        for low,high in [(1,1),(2,1),(0,float("nan"))]:
            with self.subTest(low=low,high=high),self.assertRaises(ValueError):
                builder.display_plane(np.zeros((3,3)),low,high)

    def test_existing_output_is_preserved_without_reading_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/"session";out.mkdir()
            marker=out/"annotations.csv";marker.write_text("existing human work")
            with patch.object(builder,"sha256_file")as digest:
                with self.assertRaisesRegex(ValueError,"Output exists"):
                    builder.prepare(root/builder.EXPECTED_NAME,root/"baseline.csv",out)
            digest.assert_not_called()
            self.assertEqual(marker.read_text(),"existing human work")

    def test_checksum_mismatch_creates_no_session(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,manifest,template=self.fixture(root,"a"*64)
            with patch.object(builder,"TEMPLATE",template),patch.object(builder.nd2,"ND2File")as reader:
                with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,"SHA-256 differs"):
                    builder.prepare(source,manifest,root/"session")
            reader.assert_not_called()
            self.assertFalse((root/"session").exists())
            self.assertEqual(source.read_bytes(),b"raw")

    def test_duplicate_baseline_entries_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,manifest,_=self.fixture(root)
            content=manifest.read_text();manifest.write_text(content+content.splitlines()[1]+"\n")
            with self.assertRaisesRegex(ValueError,"exactly one entry"):
                builder.baseline_row(manifest,source)

    def test_wrong_dimensions_fail_before_assets_are_written(self):
        class Wrong:
            sizes={"T":151,"C":3,"Y":512,"X":512}
            def __init__(self,path):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,manifest,template=self.fixture(root)
            with patch.object(builder,"TEMPLATE",template),patch.object(builder.nd2,"ND2File",Wrong):
                with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,"151x3x1024x1024"):
                    builder.prepare(source,manifest,root/"session")
            self.assertFalse((root/"session").exists())


if __name__=="__main__":
    unittest.main()
