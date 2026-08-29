from __future__ import annotations

from wavebench.instruments import (
    SOURCE_CONTRACT_VERSION,
    ComponentAmplitudeKind,
    HarmonicCompleteness,
    InstrumentDescriptor,
    SourceActivationPredicate,
    SourceActivationRule,
    SourceAmplitudeUnit,
    SourceAnchorField,
    SourceBasicCapabilityProfile,
    SourceBurstCapabilityProfile,
    SourceBurstMode,
    SourceConstraintApplicability,
    SourceCounterCapabilityProfile,
    SourceCounterMeasurementKind,
    SourceDescriptorExtensions,
    SourceFacetQueryContract,
    SourceFacetScope,
    SourceFeature,
    SourceFeatureCapability,
    SourceFeatureDirection,
    SourceFieldId,
    SourceFrequencyMode,
    SourceHarmonicCapabilityProfile,
    SourceHarmonicPreset,
    SourceOutputCapabilityProfile,
    SourcePulseCapabilityProfile,
    SourcePulseHoldBasis,
    SourceQueryContract,
    SourceQueryEffect,
    SourceSafetyProfile,
    SourceSweepCapabilityProfile,
    SourceSweepSpacing,
    SourceTopologyContract,
    SourceTriggerSource,
    SourceWaveformKind,
    SupportState,
)


_V2_CHANNELS = (1, 2)


def _source_extensions() -> SourceDescriptorExtensions:
    applicability = SourceConstraintApplicability()
    basic_profile = SourceBasicCapabilityProfile(
        waveform_kinds=(
            SourceWaveformKind.ARBITRARY,
            SourceWaveformKind.DC,
            SourceWaveformKind.NOISE,
            SourceWaveformKind.OTHER,
            SourceWaveformKind.PULSE,
            SourceWaveformKind.RAMP,
            SourceWaveformKind.SINE,
            SourceWaveformKind.SQUARE,
        ),
        frequency_modes=(SourceFrequencyMode.FIXED, SourceFrequencyMode.SWEEP),
        amplitude_units=(
            SourceAmplitudeUnit.DBM,
            SourceAmplitudeUnit.VPP,
            SourceAmplitudeUnit.VRMS,
        ),
        offset_readable=True,
        phase_readable=True,
        square_duty_readable=True,
    )
    output_profile = SourceOutputCapabilityProfile(
        output_readable=True,
        display_load_readable=False,
        polarity_readable=False,
    )
    burst_profile = SourceBurstCapabilityProfile(
        modes=(
            SourceBurstMode.GATED,
            SourceBurstMode.INFINITY,
            SourceBurstMode.TRIGGERED,
        ),
        trigger_sources=(
            SourceTriggerSource.EXTERNAL,
            SourceTriggerSource.INTERNAL,
            SourceTriggerSource.MANUAL,
        ),
        timing_readable=True,
        gate_readable=True,
    )
    sweep_profile = SourceSweepCapabilityProfile(
        spacing_modes=(
            SourceSweepSpacing.LINEAR,
            SourceSweepSpacing.LOGARITHMIC,
            SourceSweepSpacing.STEP,
        ),
        trigger_sources=(
            SourceTriggerSource.EXTERNAL,
            SourceTriggerSource.INTERNAL,
            SourceTriggerSource.MANUAL,
        ),
        timing_readable=True,
        marker_readable=True,
    )
    pulse_profile = SourcePulseCapabilityProfile(
        hold_modes=(SourcePulseHoldBasis.DUTY, SourcePulseHoldBasis.WIDTH),
        delay_readable=True,
        transitions_readable=True,
    )
    harmonic_profile = SourceHarmonicCapabilityProfile(
        minimum_order=2,
        maximum_order=16,
        amplitude_kinds=(ComponentAmplitudeKind.ABSOLUTE_VPP,),
        completeness_modes=(HarmonicCompleteness.PARTIAL,),
        presets=(
            SourceHarmonicPreset.ALL,
            SourceHarmonicPreset.EVEN,
            SourceHarmonicPreset.ODD,
        ),
        configured_order_readable=True,
        preset_readable=True,
    )
    counter_profile = SourceCounterCapabilityProfile(
        input_ids=("counter",),
        measurement_kinds=(
            SourceCounterMeasurementKind.DUTY_PERCENT,
            SourceCounterMeasurementKind.FREQUENCY_HZ,
            SourceCounterMeasurementKind.NEGATIVE_WIDTH_S,
            SourceCounterMeasurementKind.PERIOD_S,
            SourceCounterMeasurementKind.POSITIVE_WIDTH_S,
        ),
        configuration_readable=False,
        query_effect=SourceQueryEffect.PURE_READ,
    )
    channel_features = tuple(
        SourceFeatureCapability(
            feature=feature,
            support=SupportState.SUPPORTED,
            directions=(SourceFeatureDirection.READ,),
            scope=SourceFacetScope.CHANNEL,
            channels=(channel,),
            applicability=applicability,
            profile=profile,
        )
        for feature, profile in (
            (SourceFeature.BASIC, basic_profile),
            (SourceFeature.BURST, burst_profile),
            (SourceFeature.HARMONICS, harmonic_profile),
            (SourceFeature.OUTPUT, output_profile),
            (SourceFeature.PULSE, pulse_profile),
            (SourceFeature.SWEEP, sweep_profile),
        )
        for channel in _V2_CHANNELS
    )
    features = tuple(
        sorted(
            (
                *channel_features,
                SourceFeatureCapability(
                    feature=SourceFeature.COUNTER,
                    support=SupportState.SUPPORTED,
                    directions=(SourceFeatureDirection.READ,),
                    scope=SourceFacetScope.INPUT,
                    channels=(),
                    applicability=applicability,
                    profile=counter_profile,
                ),
            ),
            key=lambda item: (item.feature.value, item.scope.value, item.channels),
        )
    )
    return SourceDescriptorExtensions(
        contract_version=SOURCE_CONTRACT_VERSION,
        topology=SourceTopologyContract(
            channels=_V2_CHANNELS,
            input_ids=("counter",),
        ),
        features=features,
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
                    max_queries=8,
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
                    feature=SourceFeature.BURST,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.BURST,),
                    activation_any=(),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=10,
                    required=True,
                ),
                SourceFacetQueryContract(
                    feature=SourceFeature.COUNTER,
                    scope=SourceFacetScope.INPUT,
                    fields=(SourceFieldId.COUNTER,),
                    activation_any=(),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=11,
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
                                    equals=SourceWaveformKind.OTHER,
                                ),
                            ),
                        ),
                    ),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=3,
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
                SourceFacetQueryContract(
                    feature=SourceFeature.PULSE,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.PULSE,),
                    activation_any=(
                        SourceActivationRule(
                            predicates=(
                                SourceActivationPredicate(
                                    field=SourceAnchorField.WAVEFORM_KIND,
                                    equals=SourceWaveformKind.PULSE,
                                ),
                            ),
                        ),
                    ),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=6,
                ),
                SourceFacetQueryContract(
                    feature=SourceFeature.SWEEP,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.SWEEP,),
                    activation_any=(
                        SourceActivationRule(
                            predicates=(
                                SourceActivationPredicate(
                                    field=SourceAnchorField.FREQUENCY_MODE,
                                    equals=SourceFrequencyMode.SWEEP,
                                ),
                            ),
                        ),
                    ),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=16,
                ),
            ),
            max_queries=119,
            timeout_ms=5_000,
        ),
        safety_profile=SourceSafetyProfile(),
    )


def _open_driver(context):
    from .driver import DG4202Source

    return DG4202Source(
        transport=context.open_transport(),
        check_errors_after_ops=bool(context.settings["check_errors"]),
    )


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="rigol.dg4202",
        kind="source",
        display_name="RIGOL DG4000 Function/Arbitrary Waveform Generator",
        manufacturer="RIGOL Technologies",
        models=("DG4202", "DG4000"),
        aliases=(),
        capabilities=(
            "source.snapshot_v2",
            "source.idn",
            "source.errors",
            "source.status",
            "source.channel_profile",
            "source.sweep_profile",
            "source.counter_profile",
            "source.set_frequency",
            "source.set_function",
            "source.set_amplitude_vpp",
            "source.set_square_duty_cycle",
            "source.output",
            "source.arbitrary_probe",
            "source.arbitrary_upload",
        ),
        idn_patterns=("RIGOL TECHNOLOGIES,DG4",),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Installable RIGOL DG4000-series source driver for read-only channel, sweep, "
            "and counter profiles, fixed waveforms, output control, and validated DAC14 uploads."
        ),
        wavebench_min_version="0.8.25",
        wavebench_max_version="0.9.0",
        distribution="wavebench-rigol-dg4000",
        version="0.7.0",
        source="entry_point:rigol.dg4202",
        config_fields=(
            "source.resource",
            "source.driver",
            "safety_limits.max_source_vpp",
        ),
        source_extensions=_source_extensions(),
    )
