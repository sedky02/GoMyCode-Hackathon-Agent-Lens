from concurrent.futures import ThreadPoolExecutor

import httpx


def test_read_endpoints_survive_concurrent_requests(live_server):
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(lambda _: httpx.get(f"{live_server}/v1/overview").status_code, range(40)))
    assert codes == [200] * 40
