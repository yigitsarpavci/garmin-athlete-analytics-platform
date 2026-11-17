#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geriye dönük uyumluluk için morfoloji, sağlık ve özel plan mixin toplayıcısı."""

try:
    from engine.morphology_health_mixin import MorphologyHealthMixin
    from engine.custom_plan_mixin import CustomPlanMixin
except ImportError:
    from app.engine.morphology_health_mixin import MorphologyHealthMixin
    from app.engine.custom_plan_mixin import CustomPlanMixin


class SimulationHealthMixin(MorphologyHealthMixin, CustomPlanMixin):
    """Simülatör, morfoloji, sağlık yaşı, klinik tarama ve özel plan toplayıcı sınıfı."""
