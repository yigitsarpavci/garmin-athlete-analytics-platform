#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geriye dönük uyumluluk için modüler kota, protokol ve progresyon mixin toplayıcısı."""

try:
    from engine.weekly_quota_mixin import WeeklyQuotaMixin
    from engine.workout_protocols_mixin import WorkoutProtocolsMixin
    from engine.progression_debrief_mixin import ProgressionDebriefMixin
except ImportError:
    from app.engine.weekly_quota_mixin import WeeklyQuotaMixin
    from app.engine.workout_protocols_mixin import WorkoutProtocolsMixin
    from app.engine.progression_debrief_mixin import ProgressionDebriefMixin


class TrainingProtocolsMixin(WeeklyQuotaMixin, WorkoutProtocolsMixin, ProgressionDebriefMixin):
    """Haftalık esnek kota, branş/salon protokolleri ve post-workout debrief toplayıcı sınıfı."""
