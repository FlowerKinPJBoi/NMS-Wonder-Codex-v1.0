from app.models import NewDiscoverySubmission
from app.routers.new_discoveries import ALLOWED_PLATFORMS, ALLOWED_TYPES


def test_new_discovery_model_tracks_private_intake_and_public_result():
    columns = NewDiscoverySubmission.__table__.columns
    assert NewDiscoverySubmission.__tablename__ == "new_discovery_submissions"
    assert "object_key" in columns
    assert "published_discovery_id" in columns
    assert "published_image_id" in columns


def test_new_discovery_categories_and_console_platforms_are_bounded():
    assert ALLOWED_TYPES == {"Animal", "Flora", "Mineral"}
    assert {"xbox", "playstation", "switch"}.issubset(ALLOWED_PLATFORMS)
