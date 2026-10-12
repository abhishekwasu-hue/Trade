class FarmerProfile {
  const FarmerProfile({
    required this.id,
    required this.language,
    this.displayName,
    this.village,
    this.taluka,
    this.district,
    this.consentDataProcessing = false,
    this.consentWhatsapp = false,
  });

  final String id;
  final String language;
  final String? displayName;
  final String? village;
  final String? taluka;
  final String? district;
  final bool consentDataProcessing;
  final bool consentWhatsapp;

  /// Payload for the `farmer_profile` sync entity (see api sync/registry.py).
  Map<String, Object?> toPayload() => {
    'display_name': displayName,
    'language': language,
    'village': village,
    'taluka': taluka,
    'district': district,
    'consent_data_processing': consentDataProcessing,
    'consent_whatsapp': consentWhatsapp,
  };

  static FarmerProfile fromPayload(String id, Map<String, Object?> p) =>
      FarmerProfile(
        id: id,
        language: p['language']! as String,
        displayName: p['display_name'] as String?,
        village: p['village'] as String?,
        taluka: p['taluka'] as String?,
        district: p['district'] as String?,
        consentDataProcessing: p['consent_data_processing'] as bool? ?? false,
        consentWhatsapp: p['consent_whatsapp'] as bool? ?? false,
      );
}
