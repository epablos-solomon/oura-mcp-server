from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Oura MCP Server"
    app_env: str = "dev"

    oura_client_id: str = ""
    oura_client_secret: str = ""
    oura_redirect_uri: str = "http://localhost:8000/oauth/callback"
    oura_webhook_verification_token: str = ""
    oura_token_db_path: str = "/workspace/scratch/oura_tokens.sqlite3"

    oura_authorize_url: str = "https://cloud.ouraring.com/oauth/authorize"
    oura_token_url: str = "https://api.ouraring.com/oauth/token"
    oura_api_base: str = "https://api.ouraring.com/v2"

    oura_scopes: str = "daily personal email"


settings = Settings()
