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
    SourceArbitraryCapabilityProfile,
    SourceArbitraryPlaybackMode,
    SourceBasicCapabilityProfile,
    SourceBurstCapabilityProfile,
    SourceBurstMode,
    SourceConstraintApplicability,
    SourceCounterCapabilityProfile,
    SourceCounterConfigurationField,
    SourceCounterMeasurementKind,
    SourceCouplingCapabilityProfile,
    SourceCouplingDimension,
    SourceCouplingParameterKind,
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
    SourceModulationCapabilityProfile,
    SourceModulationKind,
    SourceModulationParameterKind,
    SourceModulationSource,
    SourceNoiseOverlayCapabilityProfile,
    SourceNoiseOverlayScaleKind,
    SourceOutputCapabilityProfile,
    SourcePulseCapabilityProfile,
    SourcePulseHoldBasis,
    SourceQueryContract,
    SourceQueryEffect,
    SourceSafetyProfile,
    SourceSweepCapabilityProfile,
    SourceSweepSpacing,
    SourceSyncCapabilityProfile,
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
        live_frequency_configurable=True,
        live_amplitude_vpp_configurable=True,
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
        inactive_readable=True,
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
        implicit_disable_features=(
            SourceFeature.BURST,
            SourceFeature.MODULATION,
        ),
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
    arbitrary_profile = SourceArbitraryCapabilityProfile(
        playback_modes=(SourceArbitraryPlaybackMode.UNKNOWN,),
        selection_readable=True,
        storage_metadata_readable=False,
        sample_rate_readable=False,
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
        configuration_readable=True,
        query_effect=SourceQueryEffect.PURE_READ,
        readable_configuration_fields=(
            SourceCounterConfigurationField.ATTENUATION,
            SourceCounterConfigurationField.COUPLING,
            SourceCounterConfigurationField.IMPEDANCE_OHM,
            SourceCounterConfigurationField.STATISTICS_ENABLED,
            SourceCounterConfigurationField.TRIGGER_LEVEL_V,
        ),
        configurable_fields=(
            SourceCounterConfigurationField.ATTENUATION,
            SourceCounterConfigurationField.COUPLING,
            SourceCounterConfigurationField.IMPEDANCE_OHM,
            SourceCounterConfigurationField.STATISTICS_ENABLED,
            SourceCounterConfigurationField.TRIGGER_LEVEL_V,
        ),
        enabled_configurable=True,
    )
    modulation_profile = SourceModulationCapabilityProfile(
        kinds=(
            SourceModulationKind.AM,
            SourceModulationKind.ASK,
            SourceModulationKind.FM,
            SourceModulationKind.FSK,
            SourceModulationKind.OTHER,
            SourceModulationKind.PM,
            SourceModulationKind.PSK,
            SourceModulationKind.PWM,
        ),
        sources=(
            SourceModulationSource.CHANNEL,
            SourceModulationSource.EXTERNAL,
            SourceModulationSource.INTERNAL,
        ),
        parameter_kinds=(
            SourceModulationParameterKind.DEPTH_PERCENT,
            SourceModulationParameterKind.DUTY_DEVIATION_PERCENT,
            SourceModulationParameterKind.FREQUENCY_DEVIATION_HZ,
            SourceModulationParameterKind.PHASE_DEVIATION_DEG,
            SourceModulationParameterKind.SYMBOL_RATE_HZ,
            SourceModulationParameterKind.WIDTH_DEVIATION_S,
        ),
        inactive_readable=True,
        configuration_readable=False,
    )
    coupling_profile = SourceCouplingCapabilityProfile(
        dimensions=(
            SourceCouplingDimension.AMPLITUDE,
            SourceCouplingDimension.FREQUENCY,
            SourceCouplingDimension.PHASE,
        ),
        parameter_kinds=(
            SourceCouplingParameterKind.AMPLITUDE_DEVIATION_VPP,
            SourceCouplingParameterKind.FREQUENCY_DEVIATION_HZ,
            SourceCouplingParameterKind.PHASE_DEVIATION_DEG,
        ),
        supported_channel_sets=(_V2_CHANNELS,),
        global_state_readable=True,
        reference_channel_readable=True,
        relation_graph_readable=False,
    )
    sync_profile = SourceSyncCapabilityProfile(
        enabled_readable=True,
        polarity_readable=True,
        source_channel_readable=False,
    )
    noise_overlay_profile = SourceNoiseOverlayCapabilityProfile(
        enabled_readable=True,
        scale_kinds=(SourceNoiseOverlayScaleKind.PERCENT,),
    )
    channel_features = tuple(
        SourceFeatureCapability(
            feature=feature,
            support=SupportState.SUPPORTED,
            directions=(
                (SourceFeatureDirection.CONFIGURE, SourceFeatureDirection.READ)
                if feature is SourceFeature.BASIC
                else (
                    SourceFeatureDirection.DISABLE,
                    SourceFeatureDirection.ENABLE,
                    SourceFeatureDirection.READ,
                )
                if feature is SourceFeature.OUTPUT
                else (SourceFeatureDirection.READ,)
            ),
            scope=SourceFacetScope.CHANNEL,
            channels=(channel,),
            applicability=applicability,
            profile=profile,
        )
        for feature, profile in (
            (SourceFeature.ARBITRARY, arbitrary_profile),
            (SourceFeature.BASIC, basic_profile),
            (SourceFeature.BURST, burst_profile),
            (SourceFeature.HARMONICS, harmonic_profile),
            (SourceFeature.MODULATION, modulation_profile),
            (SourceFeature.NOISE_OVERLAY, noise_overlay_profile),
            (SourceFeature.OUTPUT, output_profile),
            (SourceFeature.PULSE, pulse_profile),
            (SourceFeature.SWEEP, sweep_profile),
            (SourceFeature.SYNC, sync_profile),
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
                    directions=(
                        SourceFeatureDirection.CONFIGURE,
                        SourceFeatureDirection.DISABLE,
                        SourceFeatureDirection.ENABLE,
                        SourceFeatureDirection.READ,
                    ),
                    scope=SourceFacetScope.INPUT,
                    channels=(),
                    applicability=applicability,
                    profile=counter_profile,
                ),
                SourceFeatureCapability(
                    feature=SourceFeature.COUPLING,
                    support=SupportState.SUPPORTED,
                    directions=(SourceFeatureDirection.READ,),
                    scope=SourceFacetScope.CHANNEL_SET,
                    channels=_V2_CHANNELS,
                    applicability=applicability,
                    profile=coupling_profile,
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
                    feature=SourceFeature.ARBITRARY,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.ARBITRARY_SELECTION,),
                    activation_any=(
                        SourceActivationRule(
                            predicates=(
                                SourceActivationPredicate(
                                    field=SourceAnchorField.WAVEFORM_KIND,
                                    equals=SourceWaveformKind.ARBITRARY,
                                ),
                            ),
                        ),
                    ),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=1,
                ),
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
                    feature=SourceFeature.COUPLING,
                    scope=SourceFacetScope.CHANNEL_SET,
                    fields=(SourceFieldId.COUPLING,),
                    activation_any=(),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=5,
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
                    feature=SourceFeature.MODULATION,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.MODULATION,),
                    activation_any=(),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=2,
                    required=True,
                ),
                SourceFacetQueryContract(
                    feature=SourceFeature.NOISE_OVERLAY,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.NOISE_OVERLAY,),
                    activation_any=(),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=2,
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
                SourceFacetQueryContract(
                    feature=SourceFeature.SYNC,
                    scope=SourceFacetScope.CHANNEL,
                    fields=(SourceFieldId.SYNC,),
                    activation_any=(),
                    effect=SourceQueryEffect.PURE_READ,
                    max_queries=2,
                    required=True,
                ),
            ),
            max_queries=138,
            timeout_ms=5_000,
        ),
        safety_profile=SourceSafetyProfile(),
        v1_route_migration_enabled=False,
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
            "source.basic_configure_v2",
            "source.basic_live_configure_v2",
            "source.output_v2",
            "source.counter_configure_v2",
            "source.counter_enable_v2",
            "source.counter_measure_v2",
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
            "Installable RIGOL DG4000-series source driver for typed channel, sweep, and "
            "Counter profiles and operations, fixed waveforms, output control, and validated "
            "DAC14 uploads."
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
