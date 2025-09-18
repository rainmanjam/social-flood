import logging
import os

import tldextract

logger = logging.getLogger(__name__)


class GoogleNewsService:
    def __init__(self):
        # Configure TLDExtract with writable cache or disable caching
        cache_dir = os.path.join(os.getcwd(), ".tldextract_cache")
        try:
            os.makedirs(cache_dir, exist_ok=True)
            self.tld_extract = tldextract.TLDExtract(cache_dir=cache_dir)
            logger.debug(f"TLDExtract configured with cache directory: {cache_dir}")
        except (OSError, PermissionError):
            # If cache directory is not writable, disable caching
            self.tld_extract = tldextract.TLDExtract(cache_dir=None)
            logger.warning("TLDExtract cache disabled due to permission issues")

    # ...existing code...

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL using configured TLDExtract"""
        try:
            extracted = self.tld_extract(url)
            if extracted.suffix:
                return f"{extracted.domain}.{extracted.suffix}"
            else:
                return extracted.domain
        except Exception as e:
            logger.error(f"Error extracting domain from {url}: {e}")
            return "unknown"
