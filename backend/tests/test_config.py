from app.core.config import Settings


def test_settings_parse_json_and_csv_lists():
    settings = Settings(
        jwt_secret_key="x" * 64,
        admin_password="strong-admin-password",
        minio_secret_key="strong-minio-secret",
        cors_origins='["https://app.example", "https://api.example"]',
        internal_api_keys='["key-one", "key-two"]',
        reddit_subreddits='["netsec", "osint"]',
        telegram_channels="alpha,beta",
        x_accounts='["MiXeDCase"]',
    )

    assert settings.cors_origins == ["https://app.example", "https://api.example"]
    assert settings.internal_api_keys == ["key-one", "key-two"]
    assert settings.reddit_subreddits == ["netsec", "osint"]
    assert settings.telegram_channels == ["alpha", "beta"]
    assert settings.x_accounts == ["mixedcase"]
