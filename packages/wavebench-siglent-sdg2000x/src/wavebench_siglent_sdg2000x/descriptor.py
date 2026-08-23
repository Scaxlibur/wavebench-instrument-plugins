from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor
from wavebench.instruments.source_extensions import (
    SOURCE_CONTRACT_VERSION,
    ComponentAmplitudeKind,
    HarmonicCompleteness,
    SourceAmplitudeUnit,
    SourceActivationPredicate,
    SourceActivationRule,
    SourceAnchorField,
    SourceBasicCapabilityProfile,
    SourceConstraintApplicability,
    SourceDescriptorExtensions,
    SourceFacetQueryContract,
    SourceFacetScope,
    SourceFeature,
    SourceFeatureCapability,
    SourceFeatureDirection,
    SourceFieldId,
    SourceFrequencyMode,
    SourceHarmonicCapabilityProfile,
    SourceOutputCapabilityProfile,
    SourceQueryContract,
    SourceQueryEffect,
    SourceSafetyProfile,
    SourceTopologyContract,
    SourceWaveformKind,
    SupportState,
)


_V2_CHANNELS = (1, 2)


def _source_extensions() -> SourceDescriptorExtensions:
    """Describe the narrow, readback-proven Source V2 basic/output surface."""

    applicability = SourceConstraintApplicability()
    harmonic_disable_applicability = SourceConstraintApplicability(
        models=("SDG2122X",),
        firmware_ids=("2.01.01.39R7T2",),
    )
    basic_profile = SourceBasicCapabilityProfile(
        waveform_kinds=(
            SourceWaveformKind.PULSE,
            SourceWaveformKind.RAMP,
            SourceWaveformKind.SINE,
            SourceWaveformKind.SQUARE,
        ),
        frequency_modes=(SourceFrequencyMode.FIXED,),
        amplitude_units=(SourceAmplitudeUnit.VPP,),
        offset_readable=True,
        phase_readable=True,
        square_duty_readable=True,
    )
    output_profile = SourceOutputCapabilityProfile(
        output_readable=True,
        display_load_readable=True,
        polarity_readable=True,
    )
    basic_features = tuple(
        SourceFeatureCapability(
            feature=SourceFeature.BASIC,
            support=SupportState.SUPPORTED,
            directions=(
                SourceFeatureDirection.CONFIGURE,
                SourceFeatureDirection.READ,
            ),
            scope=SourceFacetScope.CHANNEL,
            channels=(channel,),
            applicability=applicability,
            profile=basic_profile,
        )
        for channel in _V2_CHANNELS
    )
    output_features = tuple(
        SourceFeatureCapability(
            feature=SourceFeature.OUTPUT,
            support=SupportState.SUPPORTED,
            directions=(
                SourceFeatureDirection.DISABLE,
                SourceFeatureDirection.ENABLE,
                SourceFeatureDirection.READ,
            ),
            scope=SourceFacetScope.CHANNEL,
            channels=(channel,),
            applicability=applicability,
            profile=output_profile,
        )
        for channel in _V2_CHANNELS
    )
    harmonic_disable_profile = SourceHarmonicCapabilityProfile(
        minimum_order=2,
        maximum_order=16,
        amplitude_kinds=(
            ComponentAmplitudeKind.ABSOLUTE_VPP,
            ComponentAmplitudeKind.RELATIVE_DB,
        ),
        completeness_modes=(HarmonicCompleteness.SELECTED_ONLY,),
    )
    harmonic_disable_features = tuple(
        SourceFeatureCapability(
            feature=SourceFeature.HARMONICS,
            support=SupportState.SUPPORTED,
            directions=(
                SourceFeatureDirection.DISABLE,
                SourceFeatureDirection.READ,
            ),
            scope=SourceFacetScope.CHANNEL,
            channels=(channel,),
            applicability=harmonic_disable_applicability,
            profile=harmonic_disable_profile,
        )
        for channel in _V2_CHANNELS
    )
    return SourceDescriptorExtensions(
        contract_version=SOURCE_CONTRACT_VERSION,
        topology=SourceTopologyContract(channels=_V2_CHANNELS),
        features=(*basic_features, *harmonic_disable_features, *output_features),
        query_contract=SourceQueryContract(
            anchor_fields=(
                SourceFieldId.BASIC,
                SourceFieldId.OUTPUT,
                SourceFieldId.IDENTITY,
            ),
            facets=(
                SourceFacetQueryContract(
                    feature=SourceFeature.BASIC,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.BASIC,),
                    activation_any=(),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=9,
                    required=True,
                ),
                SourceFacetQueryContract(
                    feature=SourceFeature.BASIC,
                    scope=SourceFacetScope.INSTRUMENT,
                    fields=(SourceFieldId.IDENTITY,),
                    activation_any=(),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=1,
                    required=True,
                ),
                SourceFacetQueryContract(
                    feature=SourceFeature.HARMONICS,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.HARMONICS,),
                    activation_any=(
                        SourceActivationRule(
                            predicates=(
                                SourceActivationPredicate(
                                    field=SourceAnchorField.WAVEFORM_KIND,
                                    equals=SourceWaveformKind.SINE,
                                ),
                            ),
                        ),
                    ),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=1,
                    required=True,
                ),
                SourceFacetQueryContract(
                    feature=SourceFeature.OUTPUT,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.OUTPUT,),
                    activation_any=(),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=1,
                    required=True,
                ),
            ),
            max_queries=44,
            timeout_ms=5_000,
        ),
        safety_profile=SourceSafetyProfile(),
    )


def _open_driver(context):
    from .driver import SDG2000XSource

    return SDG2000XSource(transport=context.open_transport())


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="siglent.sdg2000x",
        kind="source",
        display_name="SIGLENT SDG2000X Function/Arbitrary Waveform Generator",
        manufacturer="SIGLENT Technologies",
        models=("SDG2042X", "SDG2082X", "SDG2122X"),
        aliases=(),
        capabilities=(
            "source.idn",
            "source.status",
            "source.set_frequency",
            "source.set_function",
            "source.set_amplitude_vpp",
            "source.set_square_duty_cycle",
            "source.output",
            "source.arbitrary_probe",
            "source.snapshot_v2",
            "source.basic_configure_v2",
            "source.output_v2",
            "source.harmonics_disable_v2",
        ),
        idn_patterns=("Siglent Technologies,SDG2", "*IDN,SDG,SDG2"),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Strict identity and channel status for SIGLENT SDG2000X-series sources, "
            "with Source V2 basic/output and SDG2122X Harmonic-disable snapshots, "
            "plus core-owned fail-safe recovery."
        ),
        wavebench_min_version="0.8.24",
        wavebench_max_version="0.9.0",
        distribution="wavebench-siglent-sdg2000x",
        version="0.8.1",
        source="entry_point:siglent.sdg2000x",
        config_fields=(
            "source.resource",
            "source.driver",
            "safety_limits.max_source_vpp",
        ),
        source_extensions=_source_extensions(),
    )
