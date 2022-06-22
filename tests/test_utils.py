import pytest
from cardano_tools import utils


@pytest.fixture
def test_vectors():
    addr_bech32 = "addr1qyghraqad85ue38enxtdkmfsmxktds58msuxhqwyq87yjd2pefk9uwxnjt63hj85l8srdgfh50y7repx0ymaspz5s3msgdc7y8"
    addr_hex = "011171f41d69e9ccc4f99996db6d30d9acb6c287dc386b81c401fc493541ca6c5e38d392f51bc8f4f9e036a137a3c9e1e4267937d804548477"
    return (addr_bech32, addr_hex)


@pytest.fixture
def bad_test_vectors():
    bad_checksum = "addr1qyghraqad851e38enxtdkmfsmxktds58msuxhqwyq87yjd2pefk9uwxnjt63hj85l8srdgfh50y7repx0ymaspz5s3msgdc7y8"
    bad_charset = "addr1qyghraqad85@e38enxtdkmfsmxktds58msuxhqwyq87yjd2pefk9uwxnjt63hj85l8srdgfh50y7repx0ymaspz5s3msgdc7y8"
    bad_hrp = "addr1qyghraqad85ue38enxtdkmfsmxktds58msuxhqwyq87yjd2pefk9uwxnjt63hj85l8srdgfh50y7repx0ymaspz5s3msgdc1y8"
    bad_ord = "addr1qyghraqad85 e38enxtdkmfsmxktds58msuxhqwyq87yjd2pefk9uwxnjt63hj85l8srdgfh50y7repx0ymaspz5s3msgdc7y8"
    return (bad_checksum, bad_charset, bad_hrp, bad_ord)


def test_bech32_encode(test_vectors):
    data = bytes.fromhex(test_vectors[1])
    encoded_address = utils.bech32_encode("addr", data)
    assert encoded_address == test_vectors[0]


def test_bech32_decode(test_vectors):
    hrp, payload = utils.bech32_decode(test_vectors[0])
    hex_data = "".join(format(x, "02x") for x in payload)
    assert hex_data == test_vectors[1]


def test_bad_bech32(bad_test_vectors):
    assert (None, None) == utils.bech32_decode(bad_test_vectors[0])
    assert (None, None) == utils.bech32_decode(bad_test_vectors[1])
    assert (None, None) == utils.bech32_decode(bad_test_vectors[2])
    assert (None, None) == utils.bech32_decode(bad_test_vectors[3])
