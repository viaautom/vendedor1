import os
import hashlib
import time
import requests
import json

SHOPEE_PARTNER_ID = "18352041225"
SHOPEE_PARTNER_KEY = "BOVH3X7ZCW2KSZV6AQ6SO6PLSL3VWJEU"
GRAPHQL_ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"

def test():
    timestamp = int(time.time())
    query = """
    query($keyword: String!, $limit: Int!) {
      productOfferV2(keyword: $keyword, limit: $limit) {
        nodes {
          itemId
          productName
        }
      }
    }
    """
    payload_dict = {"query": query, "variables": {"keyword": "smart watch", "limit": 5}}
    payload = json.dumps(payload_dict)
    
    base = f"{SHOPEE_PARTNER_ID}{timestamp}{payload}{SHOPEE_PARTNER_KEY}"
    assinatura = hashlib.sha256(base.encode("utf-8")).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_PARTNER_ID}, Signature={assinatura}, Timestamp={timestamp}",
    }
    
    print("Enviando requisicao...")
    resp = requests.post(GRAPHQL_ENDPOINT, data=payload, headers=headers)
    print("Status:", resp.status_code)
    print("Body:", resp.text)

test()
