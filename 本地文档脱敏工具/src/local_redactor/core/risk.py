from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace

from local_redactor.models import (
    Category,
    DocumentModel,
    Finding,
    Modality,
    SourceLocation,
    TransformMethod,
)


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    scope: str
    score: int
    level: str
    categories: tuple[Category, ...]
    recommended_categories: tuple[Category, ...]
    finding_ids: tuple[str, ...]
    location: SourceLocation


class CombinationRiskScorer:
    """Flag task-local quasi-identifier combinations without logging source text."""

    _WEIGHTS: dict[Category, int] = {
        Category.NAME: 24,
        Category.ADDRESS: 28,
        Category.LOCATION: 18,
        Category.TIME: 18,
        Category.ORGANIZATION: 12,
        Category.DEPARTMENT: 14,
        Category.PROJECT: 10,
        Category.SYSTEM: 10,
        Category.MONEY: 8,
        Category.CASE_ID: 24,
        Category.DEVICE_ID: 20,
        Category.PUBLIC_IP: 22,
        Category.PRIVATE_IP: 18,
        Category.DOMAIN: 16,
        Category.USERNAME: 20,
        Category.VEHICLE_PLATE: 24,
        Category.ACCOUNT: 25,
        Category.EMAIL: 26,
        Category.PHONE: 26,
        Category.ID_CARD: 30,
    }
    _RECOMMENDATION_ORDER: tuple[Category, ...] = (
        Category.ADDRESS,
        Category.LOCATION,
        Category.TIME,
        Category.DEPARTMENT,
        Category.NAME,
        Category.ORGANIZATION,
        Category.PROJECT,
        Category.SYSTEM,
        Category.DEVICE_ID,
        Category.CASE_ID,
        Category.PUBLIC_IP,
        Category.PRIVATE_IP,
        Category.USERNAME,
        Category.MONEY,
    )

    def __init__(
        self,
        *,
        scope_threshold: int = 52,
        document_threshold: int = 86,
    ) -> None:
        self.scope_threshold = scope_threshold
        self.document_threshold = document_threshold

    def assess(
        self,
        document: DocumentModel,
        findings: Iterable[Finding],
    ) -> list[Finding]:
        del document  # The score intentionally depends on findings, not raw text.
        finding_list = [
            finding
            for finding in findings
            if finding.category in self._WEIGHTS
            and finding.category is not Category.COMBINATION_RISK
        ]
        grouped: dict[str, list[Finding]] = defaultdict(list)
        locations: dict[str, SourceLocation] = {}

        for finding in finding_list:
            for location in finding.locations:
                scope = self._scope_for_location(location)
                grouped[scope].append(finding)
                locations.setdefault(scope, location)

        assessments: list[RiskAssessment] = []
        for scope, scoped_findings in grouped.items():
            assessment = self._assessment(
                scope,
                scoped_findings,
                locations[scope],
            )
            if assessment.score >= self.scope_threshold and len(assessment.categories) >= 2:
                assessments.append(assessment)

        document_categories = {finding.category for finding in finding_list if finding.locations}
        if len(document_categories) >= 5 and finding_list:
            document_location = finding_list[0].locations[0]
            document_assessment = self._assessment(
                "document",
                finding_list,
                document_location,
            )
            if document_assessment.score >= self.document_threshold:
                assessments.append(document_assessment)

        max_score_by_id: dict[str, int] = defaultdict(int)
        for assessment in assessments:
            for finding_id in assessment.finding_ids:
                max_score_by_id[finding_id] = max(
                    max_score_by_id[finding_id],
                    assessment.score,
                )
        for finding in finding_list:
            if finding.id in max_score_by_id:
                finding.combination_score = max_score_by_id[finding.id]

        return [self._to_finding(assessment) for assessment in assessments]

    def _assessment(
        self,
        scope: str,
        findings: list[Finding],
        location: SourceLocation,
    ) -> RiskAssessment:
        unique_by_id = {finding.id: finding for finding in findings}
        unique_findings = tuple(unique_by_id.values())
        categories = tuple(
            sorted(
                {finding.category for finding in unique_findings},
                key=lambda category: category.value,
            )
        )
        score = sum(self._WEIGHTS[category] for category in categories)

        category_set = set(categories)
        if Category.TIME in category_set and {Category.ADDRESS, Category.LOCATION} & category_set:
            score += 18
        if {Category.ORGANIZATION, Category.DEPARTMENT} & category_set and {
            Category.PROJECT,
            Category.SYSTEM,
        } & category_set:
            score += 12
        if {Category.CASE_ID, Category.DEVICE_ID} & category_set and {
            Category.PUBLIC_IP,
            Category.PRIVATE_IP,
            Category.DOMAIN,
            Category.USERNAME,
        } & category_set:
            score += 14
        if (
            Category.NAME in category_set
            and {Category.ORGANIZATION, Category.DEPARTMENT} & category_set
        ):
            score += 10

        score = min(100, score)
        level = "high" if score >= 75 else "medium"
        recommended = tuple(
            category for category in self._RECOMMENDATION_ORDER if category in category_set
        )[:3]
        return RiskAssessment(
            scope=scope,
            score=score,
            level=level,
            categories=categories,
            recommended_categories=recommended,
            finding_ids=tuple(finding.id for finding in unique_findings),
            location=replace(location, start=None, end=None, bbox=None),
        )

    def _to_finding(self, assessment: RiskAssessment) -> Finding:
        category_names = "、".join(category.value for category in assessment.categories)
        recommendations = "、".join(
            category.value for category in assessment.recommended_categories
        )
        return Finding(
            category=Category.COMBINATION_RISK,
            modality=Modality.RELATION,
            original="",
            locations=[assessment.location],
            detector="combination-risk",
            confidence=assessment.score / 100,
            suggested_method=TransformMethod.GENERALIZE,
            preserved_semantics="保留事件主干、因果与实体关系",
            context="多个普通字段组合后可能形成可识别事件。",
            combination_score=assessment.score,
            metadata={
                "scope": assessment.scope,
                "risk_level": assessment.level,
                "categories": category_names,
                "recommended_categories": recommendations,
                "contributor_ids": assessment.finding_ids,
                "minimum_necessary": True,
            },
        )

    @staticmethod
    def _scope_for_location(location: SourceLocation) -> str:
        if location.block_id:
            return f"block:{location.part}:{location.block_id}"
        if location.sheet and location.cell:
            row_match = re.search(r"(\d+)$", location.cell)
            row = row_match.group(1) if row_match else location.cell
            return f"sheet:{location.sheet}:row:{row}"
        if location.image_id:
            return f"image:{location.image_id}"
        return f"part:{location.part}:{location.display}"


__all__ = ["CombinationRiskScorer", "RiskAssessment"]
