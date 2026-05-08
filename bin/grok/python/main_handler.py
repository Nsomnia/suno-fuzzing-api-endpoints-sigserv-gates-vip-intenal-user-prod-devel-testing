import itertools
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

class SunoFuzzer:
    def __init__(self, auth: SunoAuth, wordlist_paths=None):
        self.auth = auth
        self.base_url = "https://suno.com"  # or api.suno.com if different
        self.known_endpoints = set()  # track discovered
        self.results = []

    def load_wordlists(self):
        # Common API wordlists + Suno-specific
        words = set()
        for path in ["common.txt", "api_paths.txt", "suno_mutations.txt"]:
            try:
                with open(path) as f:
                    words.update(line.strip() for line in f if line.strip())
            except:
                pass
        # Mutations: /api/v1/, /api/admin/, /internal/, etc.
        prefixes = ["", "api/", "v1/", "v2/", "internal/", "admin/", "clerk/", "sigserv/"]
        suffixes = ["", "/list", "/get", "/create", "/update", "/delete", "/status"]
        self.words = list(words) + [p + w + s for p, w, s in itertools.product(prefixes, words, suffixes)]

    def fuzz(self, paths_to_fuzz=None, methods=["GET", "POST"], threads=10, delay=0.2):
        self.load_wordlists()
        targets = paths_to_fuzz or ["/api/"]

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = []
            for base_path in targets:
                for word in self.words:
                    for method in methods:
                        url = urljoin(self.base_url, base_path.rstrip('/') + '/' + word.lstrip('/'))
                        futures.append(executor.submit(self._test_endpoint, method, url))

                        if len(futures) % 50 == 0:
                            time.sleep(delay)

            for future in as_completed(futures):
                result = future.result()
                if result:
                    self.results.append(result)
                    print(f"[+] {result['method']} {result['url']} -> {result['status']}")

    def _test_endpoint(self, method, url):
        try:
            resp = self.auth.request(method, url, json={} if method == "POST" else None, timeout=10)
            status = resp.status_code

            interesting = status not in (404, 405, 403) or "json" in resp.headers.get("content-type", "")

            if interesting:
                try:
                    data = resp.json()
                except:
                    data = resp.text[:500]

                self.known_endpoints.add(url)

                return {
                    "method": method,
                    "url": url,
                    "status": status,
                    "length": len(resp.content),
                    "response_preview": data if isinstance(data, dict) else str(data)[:300]
                }
        except Exception as e:
            return None
        return None

    def recursive_crawl(self, start_urls, depth=2):
        # Follow links in responses, JS files, etc.
        pass  # Extend with BeautifulSoup or regex for /api/ paths in JS