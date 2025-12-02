"""
NovaSniper v2.0 Price Fetcher Service
Multi-platform price fetching with official APIs
"""
import re
import asyncio
import hashlib
import hmac
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs, quote
from abc import ABC, abstractmethod

import httpx

from app.config import settings
from app.models import Platform

logger = logging.getLogger(__name__)


class PriceResult:
    """Standardized price fetch result"""
    def __init__(
        self,
        success: bool,
        price: Optional[float] = None,
        currency: str = "USD",
        title: Optional[str] = None,
        image_url: Optional[str] = None,
        product_url: Optional[str] = None,
        availability: Optional[str] = None,
        original_price: Optional[float] = None,
        seller: Optional[str] = None,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        error: Optional[str] = None,
        raw_data: Optional[Dict] = None,
    ):
        self.success = success
        self.price = price
        self.currency = currency
        self.title = title
        self.image_url = image_url
        self.product_url = product_url
        self.availability = availability
        self.original_price = original_price
        self.seller = seller
        self.brand = brand
        self.category = category
        self.error = error
        self.raw_data = raw_data


class BasePriceFetcher(ABC):
    """Abstract base class for platform-specific fetchers"""
    
    @abstractmethod
    async def fetch_price(self, product_id: str) -> PriceResult:
        pass
    
    @abstractmethod
    def extract_product_id(self, url_or_id: str) -> Optional[str]:
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        pass


class AmazonFetcher(BasePriceFetcher):
    """
    Amazon Product Advertising API v5.0 fetcher
    Requires: AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG
    
    Sign up at: https://affiliate-program.amazon.com/
    API docs: https://webservices.amazon.com/paapi5/documentation/
    """
    
    ASIN_PATTERN = re.compile(r'(?:/dp/|/gp/product/|/ASIN/)([A-Z0-9]{10})', re.IGNORECASE)
    
    def __init__(self):
        self.access_key = settings.AMAZON_ACCESS_KEY
        self.secret_key = settings.AMAZON_SECRET_KEY
        self.partner_tag = settings.AMAZON_PARTNER_TAG
        self.region = settings.AMAZON_REGION
        self.marketplace = settings.AMAZON_MARKETPLACE
        self.host = f"webservices.{self.marketplace}"
        self.endpoint = f"https://{self.host}/paapi5/getitems"
    
    def is_configured(self) -> bool:
        return all([self.access_key, self.secret_key, self.partner_tag])
    
    def extract_product_id(self, url_or_id: str) -> Optional[str]:
        """Extract ASIN from URL or return if already an ASIN"""
        # Check if it's already an ASIN
        if re.match(r'^[A-Z0-9]{10}$', url_or_id, re.IGNORECASE):
            return url_or_id.upper()
        
        # Try to extract from URL
        match = self.ASIN_PATTERN.search(url_or_id)
        if match:
            return match.group(1).upper()
        
        return None
    
    def _sign_request(self, payload: str, timestamp: str) -> Dict[str, str]:
        """Generate AWS Signature Version 4 headers"""
        date_stamp = timestamp[:8]
        
        # Create canonical request
        method = "POST"
        canonical_uri = "/paapi5/getitems"
        canonical_querystring = ""
        
        headers_to_sign = {
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=utf-8",
            "host": self.host,
            "x-amz-date": timestamp,
            "x-amz-target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems",
        }
        
        canonical_headers = "\n".join(f"{k}:{v}" for k, v in sorted(headers_to_sign.items())) + "\n"
        signed_headers = ";".join(sorted(headers_to_sign.keys()))
        
        payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        
        canonical_request = f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        
        # Create string to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/ProductAdvertisingAPI/aws4_request"
        string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        
        # Calculate signature
        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        
        k_date = sign(f"AWS4{self.secret_key}".encode('utf-8'), date_stamp)
        k_region = sign(k_date, self.region)
        k_service = sign(k_region, "ProductAdvertisingAPI")
        k_signing = sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # Build authorization header
        authorization = f"{algorithm} Credential={self.access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        
        return {
            "Authorization": authorization,
            "Content-Encoding": "amz-1.0",
            "Content-Type": "application/json; charset=utf-8",
            "Host": self.host,
            "X-Amz-Date": timestamp,
            "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems",
        }
    
    async def fetch_price(self, product_id: str) -> PriceResult:
        """Fetch product data from Amazon PAAPI"""
        if not self.is_configured():
            return self._placeholder_price(product_id)
        
        asin = self.extract_product_id(product_id)
        if not asin:
            return PriceResult(success=False, error="Invalid ASIN or URL")
        
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        
        payload = json.dumps({
            "ItemIds": [asin],
            "PartnerTag": self.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": self.marketplace,
            "Resources": [
                "ItemInfo.Title",
                "ItemInfo.ByLineInfo",
                "ItemInfo.Classifications",
                "Images.Primary.Large",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
                "Offers.Listings.Availability.Type",
            ]
        })
        
        headers = self._sign_request(payload, timestamp)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.endpoint, content=payload, headers=headers)
                
                if response.status_code != 200:
                    logger.error(f"Amazon API error: {response.status_code} - {response.text}")
                    return PriceResult(success=False, error=f"API error: {response.status_code}")
                
                data = response.json()
                return self._parse_response(data, asin)
                
        except Exception as e:
            logger.exception(f"Amazon fetch error for {asin}")
            return PriceResult(success=False, error=str(e))
    
    def _parse_response(self, data: Dict, asin: str) -> PriceResult:
        """Parse Amazon PAAPI response"""
        try:
            items = data.get("ItemsResult", {}).get("Items", [])
            if not items:
                return PriceResult(success=False, error="Product not found")
            
            item = items[0]
            
            # Extract price
            price = None
            original_price = None
            availability = None
            
            offers = item.get("Offers", {}).get("Listings", [])
            if offers:
                listing = offers[0]
                price_info = listing.get("Price", {})
                price = price_info.get("Amount")
                
                saving_basis = listing.get("SavingBasis", {})
                original_price = saving_basis.get("Amount")
                
                avail_info = listing.get("Availability", {})
                availability = avail_info.get("Type", "Unknown")
            
            # Extract metadata
            item_info = item.get("ItemInfo", {})
            title = item_info.get("Title", {}).get("DisplayValue")
            
            byline = item_info.get("ByLineInfo", {})
            brand = byline.get("Brand", {}).get("DisplayValue")
            
            classifications = item_info.get("Classifications", {})
            category = classifications.get("ProductGroup", {}).get("DisplayValue")
            
            # Extract image
            images = item.get("Images", {})
            image_url = images.get("Primary", {}).get("Large", {}).get("URL")
            
            # Product URL
            product_url = item.get("DetailPageURL")
            
            return PriceResult(
                success=True,
                price=price,
                currency="USD",
                title=title,
                image_url=image_url,
                product_url=product_url,
                availability=availability,
                original_price=original_price,
                brand=brand,
                category=category,
                raw_data=item,
            )
            
        except Exception as e:
            logger.exception("Error parsing Amazon response")
            return PriceResult(success=False, error=f"Parse error: {e}")
    
    def _placeholder_price(self, product_id: str) -> PriceResult:
        """Generate placeholder price when API not configured"""
        asin = self.extract_product_id(product_id) or product_id
        # Deterministic pseudo-random price based on ASIN
        hash_val = int(hashlib.md5(asin.encode()).hexdigest()[:8], 16)
        price = 20.0 + (hash_val % 200) + (hash_val % 100) / 100
        
        return PriceResult(
            success=True,
            price=round(price, 2),
            currency="USD",
            title=f"Amazon Product {asin}",
            availability="placeholder",
            error="API not configured - using placeholder",
        )


class EbayFetcher(BasePriceFetcher):
    """
    eBay Shopping API / Browse API fetcher
    Requires: EBAY_APP_ID
    
    Sign up at: https://developer.ebay.com/
    """
    
    ITEM_PATTERN = re.compile(r'(?:/itm/|item=)(\d+)', re.IGNORECASE)
    
    def __init__(self):
        self.app_id = settings.EBAY_APP_ID
        self.sandbox = settings.EBAY_SANDBOX
        
        if self.sandbox:
            self.endpoint = "https://open.api.sandbox.ebay.com/shopping"
        else:
            self.endpoint = "https://open.api.ebay.com/shopping"
    
    def is_configured(self) -> bool:
        return bool(self.app_id)
    
    def extract_product_id(self, url_or_id: str) -> Optional[str]:
        """Extract eBay item ID from URL or return if already an ID"""
        if url_or_id.isdigit():
            return url_or_id
        
        match = self.ITEM_PATTERN.search(url_or_id)
        if match:
            return match.group(1)
        
        return None
    
    async def fetch_price(self, product_id: str) -> PriceResult:
        """Fetch product data from eBay Shopping API"""
        if not self.is_configured():
            return self._placeholder_price(product_id)
        
        item_id = self.extract_product_id(product_id)
        if not item_id:
            return PriceResult(success=False, error="Invalid eBay item ID or URL")
        
        params = {
            "callname": "GetSingleItem",
            "responseencoding": "JSON",
            "appid": self.app_id,
            "siteid": "0",
            "version": "967",
            "ItemID": item_id,
            "IncludeSelector": "Details,ItemSpecifics,ShippingCosts",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.endpoint, params=params)
                
                if response.status_code != 200:
                    return PriceResult(success=False, error=f"API error: {response.status_code}")
                
                data = response.json()
                return self._parse_response(data)
                
        except Exception as e:
            logger.exception(f"eBay fetch error for {item_id}")
            return PriceResult(success=False, error=str(e))
    
    def _parse_response(self, data: Dict) -> PriceResult:
        """Parse eBay Shopping API response"""
        try:
            if data.get("Ack") != "Success":
                errors = data.get("Errors", [])
                error_msg = errors[0].get("LongMessage", "Unknown error") if errors else "Unknown error"
                return PriceResult(success=False, error=error_msg)
            
            item = data.get("Item", {})
            
            # Price
            current_price = item.get("ConvertedCurrentPrice", {})
            price = current_price.get("Value")
            currency = current_price.get("CurrencyID", "USD")
            
            # Metadata
            title = item.get("Title")
            image_url = item.get("GalleryURL") or item.get("PictureURL", [None])[0]
            product_url = item.get("ViewItemURLForNaturalSearch")
            
            # Availability
            listing_status = item.get("ListingStatus")
            quantity_available = item.get("QuantityAvailable", 0)
            availability = "in_stock" if listing_status == "Active" and quantity_available > 0 else "out_of_stock"
            
            # Seller
            seller_info = item.get("Seller", {})
            seller = seller_info.get("UserID")
            
            return PriceResult(
                success=True,
                price=price,
                currency=currency,
                title=title,
                image_url=image_url,
                product_url=product_url,
                availability=availability,
                seller=seller,
                raw_data=item,
            )
            
        except Exception as e:
            logger.exception("Error parsing eBay response")
            return PriceResult(success=False, error=f"Parse error: {e}")
    
    def _placeholder_price(self, product_id: str) -> PriceResult:
        """Generate placeholder price when API not configured"""
        item_id = self.extract_product_id(product_id) or product_id
        hash_val = int(hashlib.md5(item_id.encode()).hexdigest()[:8], 16)
        price = 15.0 + (hash_val % 150) + (hash_val % 100) / 100
        
        return PriceResult(
            success=True,
            price=round(price, 2),
            currency="USD",
            title=f"eBay Item {item_id}",
            availability="placeholder",
            error="API not configured - using placeholder",
        )


class WalmartFetcher(BasePriceFetcher):
    """
    Walmart Affiliate API fetcher
    Requires: WALMART_CLIENT_ID, WALMART_CLIENT_SECRET
    
    Sign up at: https://developer.walmart.com/
    """
    
    ITEM_PATTERN = re.compile(r'(?:/ip/[^/]+/|item_id=)(\d+)', re.IGNORECASE)
    
    def __init__(self):
        self.client_id = settings.WALMART_CLIENT_ID
        self.client_secret = settings.WALMART_CLIENT_SECRET
        self.endpoint = "https://developer.api.walmart.com/api-proxy/service/affil/product/v2/items"
    
    def is_configured(self) -> bool:
        return all([self.client_id, self.client_secret])
    
    def extract_product_id(self, url_or_id: str) -> Optional[str]:
        """Extract Walmart item ID from URL"""
        if url_or_id.isdigit():
            return url_or_id
        
        match = self.ITEM_PATTERN.search(url_or_id)
        if match:
            return match.group(1)
        
        return None
    
    async def fetch_price(self, product_id: str) -> PriceResult:
        """Fetch from Walmart API"""
        if not self.is_configured():
            return self._placeholder_price(product_id)
        
        item_id = self.extract_product_id(product_id)
        if not item_id:
            return PriceResult(success=False, error="Invalid Walmart item ID or URL")
        
        headers = {
            "WM_SEC.ACCESS_TOKEN": await self._get_access_token(),
            "WM_CONSUMER.ID": self.client_id,
            "Accept": "application/json",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.endpoint}/{item_id}", headers=headers)
                
                if response.status_code != 200:
                    return PriceResult(success=False, error=f"API error: {response.status_code}")
                
                data = response.json()
                return self._parse_response(data)
                
        except Exception as e:
            logger.exception(f"Walmart fetch error for {item_id}")
            return PriceResult(success=False, error=str(e))
    
    async def _get_access_token(self) -> str:
        """Get OAuth token for Walmart API"""
        # Implement OAuth flow here
        # For now, return placeholder
        return "placeholder_token"
    
    def _parse_response(self, data: Dict) -> PriceResult:
        """Parse Walmart API response"""
        try:
            price = data.get("salePrice") or data.get("msrp")
            
            return PriceResult(
                success=True,
                price=price,
                currency="USD",
                title=data.get("name"),
                image_url=data.get("mediumImage"),
                product_url=data.get("productUrl"),
                availability="in_stock" if data.get("stock") == "Available" else "out_of_stock",
                original_price=data.get("msrp"),
                brand=data.get("brandName"),
                category=data.get("categoryPath"),
                raw_data=data,
            )
        except Exception as e:
            return PriceResult(success=False, error=f"Parse error: {e}")
    
    def _placeholder_price(self, product_id: str) -> PriceResult:
        item_id = self.extract_product_id(product_id) or product_id
        hash_val = int(hashlib.md5(item_id.encode()).hexdigest()[:8], 16)
        price = 10.0 + (hash_val % 100) + (hash_val % 100) / 100
        
        return PriceResult(
            success=True,
            price=round(price, 2),
            currency="USD",
            title=f"Walmart Product {item_id}",
            availability="placeholder",
            error="API not configured - using placeholder",
        )


class BestBuyFetcher(BasePriceFetcher):
    """
    Best Buy Products API fetcher
    Requires: BESTBUY_API_KEY
    
    Sign up at: https://developer.bestbuy.com/
    """
    
    SKU_PATTERN = re.compile(r'(?:/site/[^/]+/|skuId=)(\d+)', re.IGNORECASE)
    
    def __init__(self):
        self.api_key = settings.BESTBUY_API_KEY
        self.endpoint = "https://api.bestbuy.com/v1/products"
    
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    def extract_product_id(self, url_or_id: str) -> Optional[str]:
        """Extract Best Buy SKU from URL"""
        if url_or_id.isdigit():
            return url_or_id
        
        match = self.SKU_PATTERN.search(url_or_id)
        if match:
            return match.group(1)
        
        return None
    
    async def fetch_price(self, product_id: str) -> PriceResult:
        """Fetch from Best Buy API"""
        if not self.is_configured():
            return self._placeholder_price(product_id)
        
        sku = self.extract_product_id(product_id)
        if not sku:
            return PriceResult(success=False, error="Invalid Best Buy SKU or URL")
        
        params = {
            "apiKey": self.api_key,
            "format": "json",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.endpoint}/{sku}.json", params=params)
                
                if response.status_code != 200:
                    return PriceResult(success=False, error=f"API error: {response.status_code}")
                
                data = response.json()
                return self._parse_response(data)
                
        except Exception as e:
            logger.exception(f"Best Buy fetch error for {sku}")
            return PriceResult(success=False, error=str(e))
    
    def _parse_response(self, data: Dict) -> PriceResult:
        """Parse Best Buy API response"""
        try:
            return PriceResult(
                success=True,
                price=data.get("salePrice") or data.get("regularPrice"),
                currency="USD",
                title=data.get("name"),
                image_url=data.get("image"),
                product_url=data.get("url"),
                availability="in_stock" if data.get("inStoreAvailability") else "out_of_stock",
                original_price=data.get("regularPrice"),
                brand=data.get("manufacturer"),
                category=data.get("categoryPath", [{}])[-1].get("name") if data.get("categoryPath") else None,
                raw_data=data,
            )
        except Exception as e:
            return PriceResult(success=False, error=f"Parse error: {e}")
    
    def _placeholder_price(self, product_id: str) -> PriceResult:
        sku = self.extract_product_id(product_id) or product_id
        hash_val = int(hashlib.md5(sku.encode()).hexdigest()[:8], 16)
        price = 50.0 + (hash_val % 500) + (hash_val % 100) / 100
        
        return PriceResult(
            success=True,
            price=round(price, 2),
            currency="USD",
            title=f"Best Buy Product {sku}",
            availability="placeholder",
            error="API not configured - using placeholder",
        )


class TargetFetcher(BasePriceFetcher):
    """
    Target Redsky API fetcher
    Note: Target doesn't have a public API, this uses their internal Redsky API
    """
    
    TCIN_PATTERN = re.compile(r'(?:/p/[^/]+-|tcin=|A-)(\d+)', re.IGNORECASE)
    
    def __init__(self):
        self.api_key = settings.TARGET_API_KEY or "ff457966e64d5e877fdbad070f276d18ecec4a01"
        self.endpoint = "https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1"
    
    def is_configured(self) -> bool:
        return True  # Uses default key
    
    def extract_product_id(self, url_or_id: str) -> Optional[str]:
        """Extract Target TCIN from URL"""
        if url_or_id.isdigit() and len(url_or_id) >= 8:
            return url_or_id
        
        match = self.TCIN_PATTERN.search(url_or_id)
        if match:
            return match.group(1)
        
        return None
    
    async def fetch_price(self, product_id: str) -> PriceResult:
        """Fetch from Target Redsky API"""
        tcin = self.extract_product_id(product_id)
        if not tcin:
            return PriceResult(success=False, error="Invalid Target TCIN or URL")
        
        params = {
            "key": self.api_key,
            "tcin": tcin,
            "pricing_store_id": "3991",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.endpoint, params=params)
                
                if response.status_code != 200:
                    return self._placeholder_price(product_id)
                
                data = response.json()
                return self._parse_response(data)
                
        except Exception as e:
            logger.exception(f"Target fetch error for {tcin}")
            return self._placeholder_price(product_id)
    
    def _parse_response(self, data: Dict) -> PriceResult:
        """Parse Target Redsky API response"""
        try:
            product = data.get("data", {}).get("product", {})
            item = product.get("item", {})
            price_data = product.get("price", {})
            
            current_price = price_data.get("current_retail") or price_data.get("reg_retail")
            
            return PriceResult(
                success=True,
                price=current_price,
                currency="USD",
                title=item.get("product_description", {}).get("title"),
                image_url=item.get("enrichment", {}).get("images", {}).get("primary_image_url"),
                product_url=f"https://www.target.com/p/-/A-{item.get('tcin', '')}",
                availability="in_stock" if product.get("fulfillment", {}).get("is_out_of_stock_in_all_store_locations") == False else "limited",
                original_price=price_data.get("reg_retail"),
                brand=item.get("product_description", {}).get("bullet_descriptions", [""])[0] if item.get("product_description", {}).get("bullet_descriptions") else None,
                raw_data=product,
            )
        except Exception as e:
            return PriceResult(success=False, error=f"Parse error: {e}")
    
    def _placeholder_price(self, product_id: str) -> PriceResult:
        tcin = self.extract_product_id(product_id) or product_id
        hash_val = int(hashlib.md5(tcin.encode()).hexdigest()[:8], 16)
        price = 10.0 + (hash_val % 80) + (hash_val % 100) / 100
        
        return PriceResult(
            success=True,
            price=round(price, 2),
            currency="USD",
            title=f"Target Product {tcin}",
            availability="placeholder",
            error="Unable to fetch - using placeholder",
        )


class PriceFetcherService:
    """Main service for coordinating price fetching across platforms"""
    
    def __init__(self):
        self.fetchers: Dict[Platform, BasePriceFetcher] = {
            Platform.AMAZON: AmazonFetcher(),
            Platform.EBAY: EbayFetcher(),
            Platform.WALMART: WalmartFetcher(),
            Platform.BESTBUY: BestBuyFetcher(),
            Platform.TARGET: TargetFetcher(),
        }
    
    def get_fetcher(self, platform: Platform) -> Optional[BasePriceFetcher]:
        return self.fetchers.get(platform)
    
    async def fetch_price(self, platform: Platform, product_id: str) -> PriceResult:
        """Fetch price for a product on a specific platform"""
        fetcher = self.get_fetcher(platform)
        if not fetcher:
            return PriceResult(success=False, error=f"Unsupported platform: {platform}")
        
        return await fetcher.fetch_price(product_id)
    
    def extract_product_id(self, platform: Platform, url_or_id: str) -> Optional[str]:
        """Extract product ID for a platform"""
        fetcher = self.get_fetcher(platform)
        if not fetcher:
            return None
        return fetcher.extract_product_id(url_or_id)
    
    def is_platform_configured(self, platform: Platform) -> bool:
        """Check if a platform's API is configured"""
        fetcher = self.get_fetcher(platform)
        return fetcher.is_configured() if fetcher else False
    
    def detect_platform(self, url: str) -> Optional[Platform]:
        """Auto-detect platform from URL"""
        url_lower = url.lower()
        
        if "amazon." in url_lower or "amzn." in url_lower:
            return Platform.AMAZON
        elif "ebay." in url_lower:
            return Platform.EBAY
        elif "walmart." in url_lower:
            return Platform.WALMART
        elif "bestbuy." in url_lower:
            return Platform.BESTBUY
        elif "target." in url_lower:
            return Platform.TARGET
        
        return None
    
    async def fetch_multiple(self, items: list[Tuple[Platform, str]]) -> list[PriceResult]:
        """Fetch prices for multiple products concurrently"""
        tasks = [self.fetch_price(platform, product_id) for platform, product_id in items]
        return await asyncio.gather(*tasks)


# Global instance
price_fetcher_service = PriceFetcherService()
