from backend.services.recipe_recommendation import (
    RecipeRecommendationService,
)


def test_personal_recipes_are_always_available():
    result = RecipeRecommendationService().select(
        recipes=[
            {
                "id": "mine",
                "user_id": "u1",
                "name": "Pasta",
                "is_shared": False,
            }
        ],
        history=[],
        user_id="u1",
    )

    assert [item["id"] for item in result] == [
        "mine"
    ]
    assert (
        result[0]["_recommendation_scope"]
        == "personal"
    )


def test_uncooked_shared_recipe_is_not_recommended():
    result = RecipeRecommendationService().select(
        recipes=[
            {
                "id": "shared",
                "user_id": "u2",
                "name": "Curry",
                "is_shared": True,
            }
        ],
        history=[],
        user_id="u1",
    )

    assert result == []


def test_cooked_shared_recipe_is_recommended_after_personal():
    result = RecipeRecommendationService().select(
        recipes=[
            {
                "id": "shared",
                "user_id": "u2",
                "name": "Curry",
                "is_shared": True,
            },
            {
                "id": "mine",
                "user_id": "u1",
                "name": "Pasta",
                "is_shared": False,
            },
        ],
        history=[
            {
                "base_name": "  curry  ",
                "name": "Curry 1 porzione",
            }
        ],
        user_id="u1",
    )

    assert [item["id"] for item in result] == [
        "mine",
        "shared",
    ]
    assert (
        result[1]["_recommendation_scope"]
        == "shared_cooked"
    )
