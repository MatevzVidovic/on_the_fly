from retry_huge_warnings import polygon_collection


def test_repackages_only_concatenated_polygons_and_preserves_rings():
    a = 'POLYGON ((0 0,2 0,2 2,0 0))'
    b = 'POLYGON ((1 0,3 0,3 2,1 0))'
    assert polygon_collection(a+b) == 'MULTIPOLYGON (((0 0,2 0,2 2,0 0)), ((1 0,3 0,3 2,1 0)))'
    assert polygon_collection(a) == a
    assert polygon_collection(None) is None
    multi = 'MULTIPOLYGON (((0 0,2 0,2 2,0 0)))'
    assert polygon_collection(multi) == multi
