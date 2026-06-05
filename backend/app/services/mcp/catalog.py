from app.services.mcp.types import Capability, PricingModel, ProviderDescriptor


PROVIDERS = {
    "newapi_text_parser": ProviderDescriptor(
        name="newapi_text_parser",
        pricing_model=PricingModel.PAY_AS_YOU_GO,
        capabilities=(Capability.NUTRITION_TEXT,),
        notes="Reuse the existing New API gateway for food text parsing.",
    ),
    "newapi_vision": ProviderDescriptor(
        name="newapi_vision",
        pricing_model=PricingModel.PAY_AS_YOU_GO,
        capabilities=(Capability.NUTRITION_PHOTO,),
        notes="Reuse the existing multimodal LLM path for food photo understanding.",
    ),
    "fatsecret": ProviderDescriptor(
        name="fatsecret",
        pricing_model=PricingModel.STARTUP_FREE,
        capabilities=(Capability.NUTRITION_TEXT, Capability.NUTRITION_PHOTO),
        notes="Primary structured nutrition lookup for low-frequency startup usage.",
    ),
    "edamam": ProviderDescriptor(
        name="edamam",
        pricing_model=PricingModel.MONTHLY_SUBSCRIPTION,
        capabilities=(Capability.NUTRITION_TEXT,),
        notes="Fallback structured nutrition provider once usage justifies a subscription.",
    ),
    "logmeal": ProviderDescriptor(
        name="logmeal",
        pricing_model=PricingModel.TRIAL_ONLY,
        capabilities=(Capability.NUTRITION_PHOTO,),
        notes="Photo-food fallback during trial or demo windows.",
    ),
    "ymove": ProviderDescriptor(
        name="ymove",
        pricing_model=PricingModel.MONTHLY_SUBSCRIPTION,
        capabilities=(Capability.NUTRITION_PHOTO, Capability.MOVEMENT_VIDEO),
        notes="Fast full-stack backup for demo periods, but not the default low-cost path.",
    ),
    "mediapipe_local": ProviderDescriptor(
        name="mediapipe_local",
        pricing_model=PricingModel.LOCAL_FREE,
        capabilities=(Capability.MOVEMENT_VIDEO,),
        notes="Primary pose extraction path with near-zero marginal cost.",
    ),
    "quickpose": ProviderDescriptor(
        name="quickpose",
        pricing_model=PricingModel.FREE_TIER,
        capabilities=(Capability.MOVEMENT_VIDEO,),
        notes="Device-limited fallback for movement analysis.",
    ),
    "passio": ProviderDescriptor(
        name="passio",
        pricing_model=PricingModel.MONTHLY_CREDITS,
        capabilities=(Capability.NUTRITION_TEXT, Capability.NUTRITION_PHOTO),
        notes="Strong platform, but currently too heavy for a low-frequency interview app.",
    ),
}
