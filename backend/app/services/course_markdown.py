"""Render a validated CourseOutline as a single markdown document.

Pure function — no DB, no I/O. The endpoint at
`GET /api/v1/courses/{id}/markdown` loads the course, validates the
stored JSONB outline back into a `CourseOutline`, and calls
`outline_to_markdown` to produce the response body.
"""

from app.schemas.course import CourseOutline


def outline_to_markdown(outline: CourseOutline) -> str:
    # Build an id→text lookup so assessment "assesses" lists can show
    # the outcome statement instead of an opaque id.
    outcome_text: dict[str, str] = {}
    for o in outline.course_outcomes:
        outcome_text[o.id] = o.text
    for m in outline.modules:
        for o in m.outcomes:
            outcome_text[o.id] = o.text

    lines: list[str] = []
    lines.append(f"# {outline.title}")
    lines.append("")
    lines.append(outline.summary)
    lines.append("")
    lines.append(f"**Audience:** {outline.target_audience}  ")
    lines.append(f"**Total hours:** {outline.total_hours:g}")
    lines.append("")

    lines.append("## Course outcomes")
    lines.append("")
    for o in outline.course_outcomes:
        lines.append(f"- _{o.bloom_level.value}_: {o.text}")
    lines.append("")

    for mi, module in enumerate(outline.modules, start=1):
        lines.append(f"## Module {mi}: {module.title}")
        lines.append("")
        lines.append(module.summary)
        lines.append("")
        lines.append(f"**Estimated hours:** {module.estimated_hours:g}")
        lines.append("")
        lines.append("**Module outcomes:**")
        lines.append("")
        for o in module.outcomes:
            lines.append(f"- _{o.bloom_level.value}_: {o.text}")
        lines.append("")

        for li, lesson in enumerate(module.lessons, start=1):
            lines.append(f"### Lesson {mi}.{li}: {lesson.title}")
            lines.append("")
            lines.append(lesson.summary)
            lines.append("")
            lines.append(f"**Estimated hours:** {lesson.estimated_hours:g}")
            lines.append("")

            if lesson.prerequisite_ids:
                ids = ", ".join(f"`{p}`" for p in lesson.prerequisite_ids)
                lines.append(f"**Prerequisites:** {ids}")
                lines.append("")

            lines.append("**Objectives:**")
            lines.append("")
            for obj in lesson.objectives:
                lines.append(f"- _{obj.bloom_level.value}_: {obj.text}")
            lines.append("")

            if lesson.readings:
                lines.append("**Readings:**")
                lines.append("")
                for r in lesson.readings:
                    lines.append(f"- [{r.title}]({r.url})")
                lines.append("")

            if lesson.assessments:
                lines.append("**Assessments:**")
                lines.append("")
                for a in lesson.assessments:
                    lines.append(f"- ({a.type.value}) {a.prompt}")
                    targets = [
                        outcome_text.get(oid, oid) for oid in a.assesses_outcome_ids
                    ]
                    if targets:
                        lines.append(f"  - _Assesses:_ {'; '.join(targets)}")
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"
