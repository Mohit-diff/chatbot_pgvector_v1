from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_V1_STR: str
    PROJECT_NAME: str
    #JWT_SECRET_KEY: str
    #REFRESH_SECRET_KEY: str
    #ALGORITHM: str
    #ACCESS_TOKEN_EXPIRE_MINUTES: int
    #REFRESH_TOKEN_EXPIRE_MINUTES: int

    # Database
    #SQLALCHEMY_DATABASE_URL: str
    #DB_NAME: str
    CONNECTION_STRING: str
    PG_VECTOR_CONNECTION_STRING: str
    # BACKEND_CORS_ORIGINS: str


    #BIGCOMMERCE_CLIENT_ID: str
    #BIGCOMMERCE_CLIENT_SECRET: str
    BIGCOMMERCE_ACCESS_TOKEN: str
    BIGCOMMERCE_STORE_HASH: str

    EXTENSIVE_USERNAME: str
    EXTENSIVE_PASSWORD: str

    SLACK_SIGNING_SECRET: str
    SLACK_BOT_TOKEN: str

    #GOOGLE_API_KEY: str
    
    OPENAI_API_KEY: str

    # class Config:
    #     case_sensitive = True

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
