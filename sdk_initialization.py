from gooddata_sdk import GoodDataSdk


def initialize_sdk(hostname: str, api_token: str) -> GoodDataSdk:
    return GoodDataSdk.create(hostname, api_token)
