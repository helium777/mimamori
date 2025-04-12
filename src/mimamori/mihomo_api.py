import requests
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed


class MihomoAPI:
    def __init__(self, api_base_url: str):
        """
        Initialize the MihomoAPI with a base URL.

        Args:
            api_base_url: The base URL of the API
        """
        self.api_base_url = api_base_url

    def get_proxies(self, group_name: str) -> List[str]:
        """
        Fetch available proxies from the specified proxy group.

        Args:
            group_name: The name of the proxy group to fetch proxies from

        Returns:
            List of proxy names
        """
        group_name = requests.utils.quote(group_name)
        response = requests.get(f"{self.api_base_url}/proxies/{group_name}")
        response.raise_for_status()
        data = response.json()
        return list(data.get("all", []))

    def get_current_proxy(self, group_name: str) -> str:
        """
        Get the currently selected proxy for the specified proxy group.

        Args:
            group_name: The name of the proxy group to fetch the current proxy from

        Returns:
            Name of current proxy
        """
        group_name = requests.utils.quote(group_name)
        response = requests.get(f"{self.api_base_url}/proxies/{group_name}")
        response.raise_for_status()
        data = response.json()
        return data.get("now", "")

    def _test_single_proxy(self, proxy: str) -> tuple[str, int]:
        """
        Test the latency of a single proxy.

        Args:
            proxy: The proxy name to test

        Returns:
            Tuple of (proxy_name, latency)
        """
        proxy = requests.utils.quote(proxy)
        try:
            delay_url = f"{self.api_base_url}/proxies/{proxy}/delay?timeout=5000&url=https://www.gstatic.com/generate_204"
            response = requests.get(delay_url)
            response.raise_for_status()
            delay_data = response.json()
            return delay_data.get("delay", -1)
        except requests.RequestException:
            return -1

    def test_proxy_latencies(
        self,
        proxies: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        max_workers: int = 10,
    ) -> Dict[str, int]:
        """
        Test latency for each proxy in the list with parallel execution.

        Args:
            proxies: List of proxy names to test
            progress_callback: Optional callback function to report progress (current, total)
            max_workers: Maximum number of concurrent workers (default: 10)

        Returns:
            Dictionary mapping proxy names to latency in ms (-1 if timeout)
        """
        results = {proxy: -1 for proxy in proxies}
        total = len(proxies)
        completed = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks to the executor
            future_to_proxy = {
                executor.submit(self._test_single_proxy, proxy): proxy
                for proxy in proxies
            }

            # Process results as they complete
            for future in as_completed(future_to_proxy):
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

                latency = future.result()
                proxy = future_to_proxy[future]
                results[proxy] = latency

        return results

    def select_proxy(self, group_name: str, proxy_name: str) -> bool:
        """
        Switch to the specified proxy for the specified proxy group.

        Args:
            group_name: Name of the proxy group
            proxy_name: Name of the proxy to select

        Returns:
            True if successful, False otherwise
        """
        group_name = requests.utils.quote(group_name)
        update_url = f"{self.api_base_url}/proxies/{group_name}"
        payload = {"name": proxy_name}
        response = requests.put(update_url, json=payload)
        response.raise_for_status()
        return True
