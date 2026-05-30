"""wrapper_v2/classifier — cascade + tier-routing + register per R2 §4.4.

Re-exports from pipeline/* for now. Phase-3 will physically restructure
once D2 (detect_question_topic externalize) lands.

Currently covers:
  - language_detect    (Babel-Cascade lid.176 + P-Matrix)
  - fringe_classifier  (fringe-science / pseudoscience pre-classifier)
  - knowledge_question_classifier (knowledge-question shape detector)

Still pending Phase-3 (D2 + D7):
  - topic_match        (externalized v1 detect_question_topic monster)
  - register_detect    (consolidated from v1's multiple register-detectors)
  - tier_routing       (goal-driven funnel replacing should_engage_deep_tier)
  - babel_cascade      (rename language_detect for R2-naming consistency)

Doctrine: [[1455xl_chassis_goal_driven_funnel]] —
goal-driven funnel; [[factampel_implementation_roadmap_pixabay_classification]]
— externalize-to-config strategy.
"""

from wrapper_v2.pipeline.language_detect import (
    LangDetectResult,
)
from wrapper_v2.pipeline.fringe_classifier import (
    detect_fringe_terms,
    build_fringe_directive,
    check_and_build as check_fringe,
    FRINGE_TERMS,
)
from wrapper_v2.pipeline.knowledge_question_classifier import (
    classify_query,
    expand_search_keywords,
    build_discipline_directive,
)
from wrapper_v2.classifier.register_detect import (
    Tone,
    Irony,
    RegisterResult,
    IronyAdapter,
    register_irony_adapter,
    detect_register,
    build_system_message,
)

__all__ = [
    # language-detection (Babel-Cascade)
    "LangDetectResult",
    # fringe-classifier
    "detect_fringe_terms", "build_fringe_directive", "check_fringe",
    "FRINGE_TERMS",
    # knowledge-question-classifier
    "classify_query", "expand_search_keywords", "build_discipline_directive",
    # register-detect (D7 dedup — consolidates v1 detect_query_register
    # + detect_irony_register + auto_style_mirror_system_msg +
    # irony_register_system_msg into one typed module)
    "Tone", "Irony", "RegisterResult",
    "IronyAdapter", "register_irony_adapter",
    "detect_register", "build_system_message",
]
