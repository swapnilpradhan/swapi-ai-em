---
description: PRD Review and Update Workflow - Ensures PRD stays aligned with project changes
---

# PRD Review and Update Workflow

This workflow ensures the Product Requirements Document (PRD.md) stays current and properly versioned as the project evolves.

## When to Update the PRD

Update the PRD whenever changes affect:
- ✅ Project objectives or vision
- ✅ Feature requirements (new, modified, or removed)
- ✅ Code quality standards
- ✅ Security requirements
- ✅ Technical architecture
- ✅ Performance targets
- ✅ Testing requirements
- ✅ Success metrics or KPIs
- ✅ Release criteria
- ✅ Roadmap milestones

## PRD Update Process

### Step 1: Review Current PRD
```bash
# Open and review the current PRD
cat /Users/admin/Git/swapi-ai-em/PRD.md | head -50
```

### Step 2: Identify Affected Sections
Determine which sections need updates based on the changes made:
- Executive Summary
- Vision & Objectives
- Core Features & Requirements
- Technical Architecture
- Code Quality Standards
- Security Posture Requirements
- Performance Requirements
- Testing Requirements
- Success Metrics & KPIs
- Release Criteria
- Roadmap & Milestones

### Step 3: Determine Version Increment

**Semantic Versioning Rules:**

**MAJOR version (X.0.0)** - Increment when:
- Breaking changes to core architecture
- Fundamental shift in project objectives
- Major feature additions that change product direction
- Significant security model changes

**MINOR version (0.X.0)** - Increment when:
- New features added
- Significant requirement changes
- New code quality or security standards
- Architecture enhancements (non-breaking)

**PATCH version (0.0.X)** - Increment when:
- Bug fixes in requirements
- Clarifications or corrections
- Minor updates to metrics or targets
- Documentation improvements

### Step 4: Update PRD Sections

Edit the relevant sections in PRD.md with:
- Clear, specific changes
- Updated status indicators (✅ ⚠️ 🔴)
- New action items if applicable
- Updated metrics or targets

### Step 5: Update Version and Change Log

At the top of PRD.md:
```markdown
**Version**: X.Y.Z  
**Last Updated**: YYYY-MM-DD  
```

At the bottom in the Change Log table:
```markdown
| X.Y.Z | YYYY-MM-DD | Brief description of changes | Author |
```

### Step 6: Notify User

Always inform the user of PRD updates with:
- Version number changed (e.g., 2.0.0 → 2.1.0)
- Summary of sections updated
- Key changes made
- Impact on project alignment

## Example Update Flow

**Scenario**: Added authentication feature

1. **Review**: Check current auth requirements in SEC1
2. **Identify**: Affects Security Posture, Features, Roadmap
3. **Version**: MINOR increment (2.0.0 → 2.1.0)
4. **Update**:
   - Change SEC1 status from 🔴 to ✅
   - Update F1 requirements to include auth
   - Update Q1 roadmap to mark auth as complete
5. **Change Log**: Add entry for authentication implementation
6. **Notify**: "PRD updated to v2.1.0 - Authentication implemented"

## Automation Checklist

For every significant code change, ask:
- [ ] Does this add/modify/remove a feature?
- [ ] Does this change code quality standards?
- [ ] Does this affect security posture?
- [ ] Does this change architecture?
- [ ] Does this impact performance targets?
- [ ] Does this affect testing requirements?
- [ ] Does this change success metrics?
- [ ] Does this update release criteria?

If ANY answer is "Yes" → Update PRD

## Quick Reference

**Current PRD Location**: `/Users/admin/Git/swapi-ai-em/PRD.md`

**Current Version**: 2.0.0

**Status Indicators**:
- ✅ Complete/Good
- ⚠️ Partial/In Progress
- 🔴 Critical/Not Started

**Priority Levels**:
- P0: Critical (Must fix before production)
- P1: High (Important for production)
- P2: Medium (Nice to have)

## Best Practices

1. **Be Specific**: Don't just say "updated requirements" - specify what changed
2. **Track Impact**: Note which sections are affected by each change
3. **Maintain History**: Never delete old entries from change log
4. **Link Changes**: Reference related commits, PRs, or issues when applicable
5. **Review Regularly**: Even without changes, review PRD monthly for accuracy
6. **Stakeholder Alignment**: Major version changes should be communicated to all stakeholders

## Integration with Development Workflow

```
Code Change → Test → Review Impact → Update PRD → Commit Both
```

Always commit PRD updates in the same PR/commit as the code changes they document.

## Monitoring PRD Health

Monthly review checklist:
- [ ] All status indicators are accurate
- [ ] Roadmap dates are realistic
- [ ] Success metrics are being tracked
- [ ] Security requirements reflect current threats
- [ ] Code quality standards are being met
- [ ] Version number is current
- [ ] Change log is complete

---

**Last Updated**: 2026-03-25  
**Maintained By**: Development Team  
**Review Frequency**: After every significant change + Monthly review
