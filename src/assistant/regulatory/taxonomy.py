"""Transparent regulatory-theme taxonomy for candidate discovery."""

from __future__ import annotations

from pydantic import BaseModel


class RegulatoryTheme(BaseModel):
    id: str
    label: str
    terms: list[str]
    reason_template: str


THEMES: tuple[RegulatoryTheme, ...] = (
    RegulatoryTheme(
        id="food_safety",
        label="Food safety and hygiene",
        terms=["food", "allergen", "hygiene", "temperature control", "food safety", "fsa"],
        reason_template="mentions food, hygiene or allergen controls that may need food-safety review",
    ),
    RegulatoryTheme(
        id="fuel_environment",
        label="Fuel, EV charging and environmental operations",
        terms=["fuel", "petrol", "diesel", "forecourt", "ev charging", "chargepoint", "electric vehicle", "environmental"],
        reason_template="mentions fuel, charging or environmental operations that may need external guidance review",
    ),
    RegulatoryTheme(
        id="employment_training",
        label="Employment, staffing and training",
        terms=["employee", "employment", "staff", "training", "competency", "working time", "contractor"],
        reason_template="mentions staffing, employment or training obligations that may need policy review",
    ),
    RegulatoryTheme(
        id="health_safety",
        label="Health, safety and incident controls",
        terms=["health and safety", "risk assessment", "incident", "accident", "ppe", "fire safety", "hse"],
        reason_template="mentions safety controls or incident handling that may need health-and-safety review",
    ),
    RegulatoryTheme(
        id="data_privacy",
        label="Data protection and privacy",
        terms=["personal data", "privacy", "gdpr", "data protection", "customer data", "retention"],
        reason_template="mentions personal/customer data handling that may need privacy review",
    ),
    RegulatoryTheme(
        id="financial_tax",
        label="Financial, fiscal and tax references",
        terms=["vat", "tax", "invoice", "fiscal", "hmrc", "duty", "financial", "margin"],
        reason_template="mentions tax, invoice or fiscal concepts that may need financial compliance review",
    ),
    RegulatoryTheme(
        id="product_compliance",
        label="Product compliance and standards",
        terms=["product compliance", "recall", "labelling", "labeling", "ce mark", "ukca", "standard"],
        reason_template="mentions product standards, recalls or labelling that may need compliance review",
    ),
    RegulatoryTheme(
        id="site_operations",
        label="Site operations, licences and inspections",
        terms=["site operations", "premises", "licence", "license", "permit", "inspection", "audit"],
        reason_template="mentions premises, licences or inspections that may need site-operations review",
    ),
)


THEME_BY_ID = {theme.id: theme for theme in THEMES}
