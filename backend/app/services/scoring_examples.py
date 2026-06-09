from collections import Counter
from typing import Any


FewShotCase = dict[str, str | int]
RegressionCase = dict[str, str | int]


SCORING_FEW_SHOT_CASES: tuple[FewShotCase, ...] = (
    {
        "row_id": 124,
        "lead_score": "GD",
        "visa_category": "Accompanying Spouse",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Accompanying spouse enquiry. Married to a South African citizen.",
        "reason": "Australian national. Qualifies.",
    },
    {
        "row_id": 139,
        "lead_score": "GD",
        "visa_category": "General Work Visa",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "General Work Visa enquiry with an offer and substantial earnings signal.",
        "reason": "Hungarian national, earns a substantial amount.",
    },
    {
        "row_id": 145,
        "lead_score": "GD",
        "visa_category": "Relative's Spouse Visa",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Accompanying spouse enquiry. Married to a South African citizen.",
        "reason": "Australian national, meets the requirements.",
    },
    {
        "row_id": 127,
        "lead_score": "GD",
        "visa_category": "Consultation",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Completed the Xpatweb VPC questionnaire with complete facts.",
        "reason": "Lead filled form completely and appears to be a high net worth individual.",
    },
    {
        "row_id": 160,
        "lead_score": "GD",
        "visa_category": "PR (Financially Independent)",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Zimbabwean national. Has R12 million net worth and intends business activity.",
        "reason": "Meets Financial Independence PR requirements and is high net worth.",
    },
    {
        "row_id": 14,
        "lead_score": "GD",
        "visa_category": "Retired Person Visa",
        "lead_source": "RSA007 - Retire in South Africa",
        "additional_info": "Has monthly retirement income and liquid net worth above the threshold.",
        "reason": "Meets the requirements for a Retired Person Visa and is high net worth.",
    },
    {
        "row_id": 131,
        "lead_score": "GD",
        "visa_category": "Business Visa",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Business Visa enquiry from a lead intending to establish or invest in a business.",
        "reason": "Meets the requirements for a Business Visa and is high net worth.",
    },
    {
        "row_id": 6,
        "lead_score": "GD",
        "visa_category": "Permanent Residence Permit",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Permanent Residence based on a Critical Skills Work Visa.",
        "reason": "Has a job and a critical-skill basis, indicating ability to use services.",
    },
    {
        "row_id": 10,
        "lead_score": "GD",
        "visa_category": "Remote Work Visa",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Remote Work Visa enquiry with annual salary exceeding R650,000.",
        "reason": "Meets Remote Work Visa income requirements and is high net worth.",
    },
    {
        "row_id": 95,
        "lead_score": "GD",
        "visa_category": "Retired Person Visa",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Has irrevocable monthly income and net worth above R1.8 million.",
        "reason": "Meets the requirements for a Retired Person Visa and is high net worth.",
    },
    {
        "row_id": 176,
        "lead_score": "MF",
        "visa_category": "Relative's Visa",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Accompanying spouse enquiry in a common-law relationship.",
        "reason": "Meets the requirements and is from a first world country.",
    },
    {
        "row_id": 159,
        "lead_score": "MF",
        "visa_category": "PR (Financially Independent)",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Nigerian national claiming R12 million net worth.",
        "reason": "Potential Financial Independence PR but nationality creates uncertainty.",
    },
    {
        "row_id": 126,
        "lead_score": "MF",
        "visa_category": "Visa Assessment",
        "lead_source": "Telephone Enquiry",
        "additional_info": "Corporate lead requesting work permit assistance for an employee.",
        "reason": "Corporate lead, but affordability is not yet clear.",
    },
    {
        "row_id": 133,
        "lead_score": "MF",
        "visa_category": "Visitors Visa Section 11(6)",
        "lead_source": "Organic www.workpermitsouthafrica.co.za",
        "additional_info": "Currently has a valid point of entry stamp and a long-term relationship.",
        "reason": "Qualifies for the category but is not a high net worth individual.",
    },
    {
        "row_id": 150,
        "lead_score": "MF",
        "visa_category": "Africa Work Permit",
        "lead_source": "Telephone Enquiry",
        "additional_info": "Corporate lead requesting assistance with six work permits for Lesotho.",
        "reason": "Timing may reduce conversion, but they will need the visas.",
    },
    {
        "row_id": 7,
        "lead_score": "MF",
        "visa_category": "Visa Verification",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Wants to verify a Permanent Residence Permit for a South African ID application.",
        "reason": "Verification work is usually MF.",
    },
    {
        "row_id": 112,
        "lead_score": "MF",
        "visa_category": "Visa Verification",
        "lead_source": "Telephone Enquiry",
        "additional_info": "Corporate lead requesting assistance with visa verification.",
        "reason": "Corporate verification lead. Telephone enquiry verification is usually MF.",
    },
    {
        "row_id": 115,
        "lead_score": "MF",
        "visa_category": "Visa Verification",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Individual requiring assistance for a driver's licence.",
        "reason": "Verification-related lead; worth follow-up but not premium.",
    },
    {
        "row_id": 143,
        "lead_score": "MD",
        "visa_category": "Permanent Residence Permit",
        "lead_source": "XP281 - Permanent Residence",
        "additional_info": "PR via relatives route. Married and residing in South Africa for longer than five years.",
        "reason": "Meets requirements but no further value information is available.",
    },
    {
        "row_id": 16,
        "lead_score": "MD",
        "visa_category": "Undesirable Status",
        "lead_source": "Telephone Enquiry",
        "additional_info": "Individual requesting overstay visa assistance on behalf of a friend.",
        "reason": "First world country lead but unlikely to pay much.",
    },
    {
        "row_id": 186,
        "lead_score": "MD",
        "visa_category": "Visa Assessment",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Critical Skills Work Visa enquiry with uncertain qualification and salary indicators.",
        "reason": "May not qualify; visa assessment costing should be sent.",
    },
    {
        "row_id": 125,
        "lead_score": "MD",
        "visa_category": "Visa Verification",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Individual visa verification request.",
        "reason": "Individual verification is usually MD.",
    },
    {
        "row_id": 11,
        "lead_score": "MD",
        "visa_category": "Relative's Visa",
        "lead_source": "XP334 - Points-Based System",
        "additional_info": "Parent is a South African citizen.",
        "reason": "Meets requirements but has no further information to qualify value.",
    },
    {
        "row_id": 4,
        "lead_score": "MD",
        "visa_category": "Litigation",
        "lead_source": "XP359 - Appeals",
        "additional_info": "Company email but likely low salary position for General Work Visa escalation.",
        "reason": "Unlikely to have a high enough paying position to qualify strongly.",
    },
    {
        "row_id": 157,
        "lead_score": "BD",
        "visa_category": "Accompanying Child Visa",
        "lead_source": "Organic www.workpermitsouthafrica.co.za",
        "additional_info": "Accompanying child under 18 with parent or guardian on TRV.",
        "reason": "Accompanying child with a TRV is usually a bad lead.",
    },
    {
        "row_id": 43,
        "lead_score": "BD",
        "visa_category": "Overstay Upliftment",
        "lead_source": "XP349 - Visa Appeals",
        "additional_info": "Wants to appeal a Visitor's Visa Section 11(1) decision.",
        "reason": "We cannot appeal Visitor's Visas in terms of Section 11(1).",
    },
    {
        "row_id": 99,
        "lead_score": "BD",
        "visa_category": "Remote Work Visa",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Remote Work lead that came through WhatsApp.",
        "reason": "WhatsApp-origin leads in this pattern are historically bad.",
    },
    {
        "row_id": 81,
        "lead_score": "BD",
        "visa_category": "e-Visa",
        "lead_source": "XP333 - Points-Based System",
        "additional_info": "e-Visa request with no premium service signal.",
        "reason": "e-Visas are historically BD leads.",
    },
    {
        "row_id": 119,
        "lead_score": "BD",
        "visa_category": "Chinese Visa",
        "lead_source": "Organic www.xpatweb.com",
        "additional_info": "Chinese M Visa request.",
        "reason": "Chinese M Visa requests are historically bad leads.",
    },
    {
        "row_id": 161,
        "lead_score": "BD",
        "visa_category": "PR (Financially Independent)",
        "lead_source": "Organic www.workpermitsouthafrica.co.za",
        "additional_info": "Malawi national claiming R12 million cash net worth.",
        "reason": "Historical data flags honesty concerns for this pattern.",
    },
)


SCORING_REGRESSION_CASES: tuple[RegressionCase, ...] = (
    *(
        {
            "row_id": row_id,
            "expected_score": "GD",
            "visa_category": "Retired Person Visa",
            "lead_source": lead_source,
            "additional_info": "Retired Person Visa enquiry with retirement income or net worth indicators.",
            "reason": "Meets Retired Person Visa requirements and is high net worth.",
        }
        for row_id, lead_source in (
            (98, "Organic www.retireinsouthafrica.com"),
            (107, "Organic www.xpatweb.com"),
            (91, "RSA024 - Why You Should Retirement In SA"),
            (51, "RSA024 - Why You Should Retirement In SA"),
            (100, "Organic www.xpatweb.com"),
            (30, "RSA024 - Why You Should Retirement In SA"),
            (19, "RSA007 - Retire in South Africa"),
            (38, "RSA024 - Why You Should Retirement In SA"),
            (46, "RSA007 - Retire in South Africa"),
            (108, "Organic www.retireinsouthafrica.com"),
            (69, "RSA024 - Why You Should Retirement In SA"),
            (59, "RSA024 - Why You Should Retirement In SA"),
        )
    ),
    *(
        {
            "row_id": row_id,
            "expected_score": "MF",
            "visa_category": visa_category,
            "lead_source": lead_source,
            "additional_info": additional_info,
            "reason": reason,
        }
        for row_id, visa_category, lead_source, additional_info, reason in (
            (
                190,
                "Visa Assessment",
                "Telephone Enquiry",
                "Corporate lead regarding 11 undocumented workers with fake papers.",
                "May not qualify; visa assessment costing sent.",
            ),
            (
                116,
                "Visa Verification",
                "Telephone Enquiry",
                "Corporate lead requesting visa verification assistance.",
                "Corporate verification lead. Always MF.",
            ),
            (
                117,
                "Visa Verification",
                "Telephone Enquiry",
                "Corporate lead requesting visa verification assistance.",
                "Corporate verification lead. Always MF.",
            ),
            (
                111,
                "Visa Verification",
                "Organic www.xpatweb.com",
                "Corporate lead requesting visa verification assistance.",
                "Corporate verification lead. Always MF.",
            ),
            (
                18,
                "Visa Verification",
                "Telephone Enquiry",
                "Corporate lead requesting visa verification assistance.",
                "Corporate verification lead. Always MF.",
            ),
            (
                153,
                "Visa Verification",
                "Telephone Enquiry",
                "Corporate lead requesting work permit verification.",
                "Corporate Visa Verification is usually MF.",
            ),
        )
    ),
    *(
        {
            "row_id": row_id,
            "expected_score": "MD",
            "visa_category": visa_category,
            "lead_source": lead_source,
            "additional_info": additional_info,
            "reason": reason,
        }
        for row_id, visa_category, lead_source, additional_info, reason in (
            (
                156,
                "Visa Verification",
                "Organic www.xpatweb.com",
                "Individual General Work Visa verification request.",
                "Individual Visa Verification is usually MD.",
            ),
            (
                34,
                "Litigation",
                "XP359 - Appeals",
                "Permanent Residency escalation with pending duration.",
                "Meets requirements but no further information was received.",
            ),
            (
                92,
                "Appeal Application",
                "XP349 - Visa Appeals",
                "Appeal enquiry for South African rejection.",
                "Meets requirements but no further information was received.",
            ),
            (
                40,
                "Study Visa",
                "XP290 - Visa Facilitation Service (SA)",
                "Study Visa enquiry with limited detail.",
                "Meets study visa requirements but provides no further information.",
            ),
            (
                200,
                "Visa Assessment",
                "Telephone Enquiry",
                "Corporate lead requesting work permit application for a Mozambican employee.",
                "May not qualify; visa assessment costing sent.",
            ),
            (
                68,
                "Litigation",
                "XP359 - Appeals",
                "Study Visa escalation pending more than the usual period.",
                "Meets requirements but no further information was received.",
            ),
            (
                188,
                "Visa Assessment",
                "Telephone Enquiry",
                "General Work Visa questionnaire with high school education and unclear offer.",
                "May not qualify; visa assessment costing sent.",
            ),
            (
                123,
                "Visitors Visa Section 11(6)",
                "Organic www.workpermitsouthafrica.co.za",
                "Relatives/spousal visitor enquiry with married relationship.",
                "Meets requirements but no further information to qualify value.",
            ),
            (
                33,
                "Appeal Application",
                "XP349 - Visa Appeals",
                "Appeal enquiry for South African rejection.",
                "Meets requirements but no further information was received.",
            ),
            (
                201,
                "Visa Assessment",
                "Telephone Enquiry",
                "Corporate lead requesting two visas for employees.",
                "May not qualify; visa assessment costing sent.",
            ),
        )
    ),
    *(
        {
            "row_id": row_id,
            "expected_score": "BD",
            "visa_category": visa_category,
            "lead_source": lead_source,
            "additional_info": additional_info,
            "reason": reason,
        }
        for row_id, visa_category, lead_source, additional_info, reason in (
            (
                169,
                "Relative's Visa",
                "Organic www.xpatweb.com",
                "Child of a citizen or permanent resident with expiring visa facts.",
                "Historically bad despite potentially meeting some requirements.",
            ),
            (28, "TBC", "RSA024 - Why You Should Retirement In SA", "Medical insurance enquiry.", "Not relevant to services."),
            (8, "Visitors Visa Section 11(1)", "Organic www.xpatweb.com", "Visitor 11(1) request.", "Visa-exempt short visitor route is a bad lead."),
            (58, "Visitors Visa Section 11(1)", "Organic www.xpatweb.com", "Visitor 11(1) request.", "Visa-exempt short visitor route is a bad lead."),
            (77, "TR Diagnostic", "XP349 - Visa Appeals", "Refugee-related work visa diagnostic.", "Refugee pattern is historically bad."),
            (158, "Critical Skills Work Visa", "Organic www.xpatweb.com", "Critical Skills enquiry with weak qualification facts.", "Does not qualify for Critical Skills Work Visa."),
            (144, "Relative's Visa", "Organic www.xpatweb.com", "Long-term relationship and visa about to expire.", "Visa was about to expire."),
            (74, "Appeal Application", "XP349 - Visa Appeals", "Appeal received more than 15 days after rejection.", "Late appeal; cannot assist."),
            (85, "Expediting the application", "XP349 - Visa Appeals", "Appeal/expediting request received more than 15 days after rejection.", "Late appeal; cannot assist."),
            (3, "Visitors Visa Section 11(1)", "Organic www.xpatweb.com", "Visitor 11(1) request.", "Visa-exempt short visitor route is a bad lead."),
            (198, "Visa Assessment", "Organic www.xpatweb.com", "Visitor 11(1)(b)(iii) Research Visa assessment with limited facts.", "May not qualify; visa assessment costing sent."),
            (181, "Relative's Visa", "XP333 - Points-Based System", "Long-term relationship with expired visa date.", "Visa already expired."),
        )
    ),
)


def score_distribution(cases: tuple[dict[str, Any], ...], score_key: str) -> dict[str, int]:
    return dict(Counter(str(case[score_key]) for case in cases))


def render_few_shot_examples() -> str:
    lines: list[str] = []
    for case in SCORING_FEW_SHOT_CASES:
        lines.append(
            "INPUT: "
            f"{case['visa_category']} | {case['lead_source']} | {case['additional_info']}\n"
            f"OUTPUT: {case['lead_score']} | {case['reason']}"
        )
    return "\n\n".join(lines)
