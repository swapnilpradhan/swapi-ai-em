---
description: PRD Review and Update Workflow - Ensures PRD stays aligned with project changes
---

# PRD Review and Update Workflow

**STANDARDIZED TEMPLATE - Copy to any project's `.windsurf/workflows/prd-update.md`**

This workflow ensures the Product Requirements Document (PRD.md) stays current and properly versioned as the project evolves.

---

## Setup Instructions

### 1. Copy This File
```bash
# Copy to your project's workflow directory
cp prd-workflow-template.md <PROJECT_ROOT>/.windsurf/workflows/prd-update.md
```

### 2. Update Project-Specific Paths
Replace `{{PROJECT_ROOT}}` with your actual project path:
- Default: `/path/to/your/project`
- Example: `/Users/admin/Git/my-project`

### 3. Customize Sections (Optional)
Adjust the "Identify Affected Sections" list based on your PRD structure.

---

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

---

## PRD Update Process

### Step 1: Review Current PRD
```bash
# Open and review the current PRD
cat {{PROJECT_ROOT}}/PRD.md | head -50

# Or view specific sections
grep -A 20 "## Core Features" {{PROJECT_ROOT}}/PRD.md
```

### Step 2: Identify Affected Sections

Determine which sections need updates based on the changes made:

**Common PRD Sections:**
- Executive Summary
- Vision & Objectives
- Target Audience
- Core Features & Requirements
- Technical Architecture
- Code Quality Standards
- Security Posture Requirements
- Performance Requirements
- Testing Requirements
- Success Metrics & KPIs
- Release Criteria
- Roadmap & Milestones

**Note**: Adjust this list to match your PRD structure.

### Step 3: Determine Version Increment

**Semantic Versioning Rules:**

#### MAJOR version (X.0.0)
Increment when:
- Breaking changes to core architecture
- Fundamental shift in project objectives
- Major feature additions that change product direction
- Significant security model changes
- Breaking API changes

**Examples:**
- Microservices → Serverless architecture
- Single-tenant → Multi-tenant
- REST API → GraphQL

#### MINOR version (0.X.0)
Increment when:
- New features added
- Significant requirement changes
- New code quality or security standards
- Architecture enhancements (non-breaking)
- New integrations or services

**Examples:**
- Adding authentication system
- Implementing new agent/service
- Adding CI/CD pipeline
- New monitoring/observability

#### PATCH version (0.0.X)
Increment when:
- Bug fixes in requirements
- Clarifications or corrections
- Minor updates to metrics or targets
- Documentation improvements
- Status indicator updates

**Examples:**
- Fixing typos or unclear requirements
- Updating test coverage metrics
- Clarifying existing requirements
- Updating completion status

### Step 4: Update PRD Sections

Edit the relevant sections in PRD.md with:

1. **Clear, specific changes**
   - What changed
   - Why it changed
   - Impact on other sections

2. **Updated status indicators**
   - ✅ Complete/Good
   - ⚠️ Partial/In Progress
   - 🔴 Critical/Not Started

3. **New action items** (if applicable)
   - What needs to be done
   - Who is responsible
   - Target completion date

4. **Updated metrics or targets**
   - Current values
   - Target values
   - Progress tracking

### Step 5: Update Version and Change Log

**At the top of PRD.md:**
```markdown
**Version**: X.Y.Z  
**Last Updated**: YYYY-MM-DD  
**Status**: [Active Development | Beta | Production]
```

**At the bottom in the Change Log table:**
```markdown
### Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| X.Y.Z | YYYY-MM-DD | Brief description of changes | Your Name |
```

**Change Log Best Practices:**
- Be specific about what changed
- Reference section IDs (e.g., "Updated SEC1, F3")
- Keep entries concise but informative
- Include author/team name

### Step 6: Notify Stakeholders

Always inform stakeholders of PRD updates with:
- Version number changed (e.g., 2.0.0 → 2.1.0)
- Summary of sections updated
- Key changes made
- Impact on project alignment
- Action items (if any)

**Notification Template:**
```
📋 PRD Updated: v{OLD} → v{NEW}

Sections Updated:
- {Section 1}: {Change description}
- {Section 2}: {Change description}

Key Changes:
- {Change 1}
- {Change 2}

Impact: {How this affects the project}

Action Items:
- [ ] {Action 1}
- [ ] {Action 2}
```

---

## Example Update Flow

### Scenario: Added Authentication Feature

**1. Review**: Check current auth requirements in Security section

**2. Identify Affected Sections**:
- Security Posture Requirements
- Core Features & Requirements
- Technical Architecture
- Roadmap & Milestones

**3. Determine Version**: MINOR increment (2.0.0 → 2.1.0)
- New feature added
- Non-breaking change
- Significant functionality

**4. Update PRD**:
```markdown
## Security Posture Requirements

### SEC1: Authentication & Authorization
**Status**: 🔴 → ✅ COMPLETE

**Implementation**:
- ✅ JWT-based authentication
- ✅ Role-based access control (RBAC)
- ✅ API key management
- ✅ Session management

**Changes**: Implemented full authentication system with JWT tokens,
RBAC for user/admin roles, and API key support for service-to-service
communication.
```

**5. Update Version**:
```markdown
**Version**: 2.1.0  
**Last Updated**: 2026-03-25
```

**6. Add Change Log Entry**:
```markdown
| 2.1.0 | 2026-03-25 | Implemented authentication (SEC1), added RBAC and API keys | Dev Team |
```

**7. Notify**:
```
📋 PRD Updated: v2.0.0 → v2.1.0

Sections Updated:
- SEC1: Authentication & Authorization (🔴 → ✅)
- F1: Core Features (added auth requirement)
- Roadmap Q1: Marked authentication complete

Key Changes:
- Implemented JWT authentication
- Added RBAC (user, admin, readonly roles)
- API key management for services

Impact: All API endpoints now require authentication. This addresses
critical security gap (P0 requirement).
```

---

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
- [ ] Does this affect roadmap milestones?

**If ANY answer is "Yes"** → Update PRD

---

## Quick Reference

### Project Configuration

**PRD Location**: `{{PROJECT_ROOT}}/PRD.md`

**Current Version**: Check top of PRD.md

**Workflow Location**: `{{PROJECT_ROOT}}/.windsurf/workflows/prd-update.md`

### Status Indicators

- ✅ **Complete/Good**: Implemented, working, requirement met
- ⚠️ **Partial/In Progress**: Partially implemented, work ongoing
- 🔴 **Critical/Not Started**: Not started, critical gap, must fix

### Priority Levels

- **P0**: Critical - Must fix before production
- **P1**: High - Important for production
- **P2**: Medium - Nice to have
- **P3**: Low - Future consideration

### Common Commands

```bash
# View current PRD version
head -10 {{PROJECT_ROOT}}/PRD.md | grep "Version"

# View recent changes
tail -30 {{PROJECT_ROOT}}/PRD.md

# Search for specific requirement
grep -n "SEC1\|CQ1\|F1" {{PROJECT_ROOT}}/PRD.md

# Count status indicators
grep -o "✅\|⚠️\|🔴" {{PROJECT_ROOT}}/PRD.md | sort | uniq -c

# View roadmap
grep -A 20 "## Roadmap" {{PROJECT_ROOT}}/PRD.md
```

---

## Best Practices

### Do's ✅

- ✅ Update PRD immediately after code changes
- ✅ Be specific in change descriptions
- ✅ Keep status indicators current
- ✅ Increment version consistently
- ✅ Maintain complete change log
- ✅ Review monthly even without changes
- ✅ Commit PRD with related code changes
- ✅ Notify stakeholders of major changes

### Don'ts ❌

- ❌ Don't skip PRD updates "for later"
- ❌ Don't use vague change descriptions
- ❌ Don't delete old change log entries
- ❌ Don't skip version increments
- ❌ Don't commit code without updating PRD
- ❌ Don't let PRD drift from reality
- ❌ Don't forget to notify stakeholders

---

## Integration with Development Workflow

### Recommended Git Workflow

```bash
# 1. Create feature branch
git checkout -b feature/new-feature

# 2. Make code changes
# ... implement feature ...

# 3. Update PRD
# - Review affected sections
# - Update status indicators
# - Increment version
# - Add change log entry

# 4. Commit both together
git add src/ PRD.md
git commit -m "feat: Add new feature (PRD v2.1.0)"

# 5. Push and create PR
git push origin feature/new-feature
```

### PR Description Template

```markdown
## Changes
- Implemented [feature/fix]
- Updated [components]

## PRD Updates
- Version: 2.0.0 → 2.1.0
- Sections: [List sections updated]
- Status: [Status changes]

## Testing
- [ ] Unit tests added
- [ ] Integration tests passed
- [ ] PRD aligned with changes
```

---

## Monthly Review Checklist

Even without changes, review PRD monthly:

- [ ] All status indicators (✅ ⚠️ 🔴) are accurate
- [ ] Roadmap dates are realistic
- [ ] Success metrics are being tracked
- [ ] Security requirements reflect current threats
- [ ] Code quality standards are being met
- [ ] Performance targets are current
- [ ] Version number is up to date
- [ ] Change log is complete
- [ ] No orphaned or outdated requirements
- [ ] Dependencies and tech stack are current

---

## Customization Guide

### For Your Project

1. **Replace `{{PROJECT_ROOT}}`** with actual path
2. **Adjust PRD sections** to match your structure
3. **Customize status indicators** if needed
4. **Add project-specific requirements** to checklist
5. **Update priority levels** to match your process
6. **Modify version rules** if using different scheme

### Example Customizations

**Different Version Scheme:**
```markdown
# If using date-based versioning
Version: YYYY.MM.PATCH
Example: 2026.03.1
```

**Additional Status Indicators:**
```markdown
- 🟢 Verified/Tested
- 🟡 Under Review
- ⚫ Deprecated
```

**Custom Priority Levels:**
```markdown
- P0: Blocker
- P1: Critical
- P2: High
- P3: Medium
- P4: Low
```

---

## Troubleshooting

### PRD Out of Sync?

1. Run full review of all sections
2. Compare PRD with actual implementation
3. Update all status indicators
4. Increment version (PATCH for sync)
5. Add change log: "Synchronized PRD with implementation"

### Version Confusion?

- **Changed behavior?** → MAJOR
- **Added feature?** → MINOR
- **Fixed/clarified?** → PATCH
- **Still unsure?** → Default to MINOR

### Missed Updates?

1. Update immediately (better late than never)
2. Note in change log: "Retroactive update for [feature]"
3. Use current date for change log entry
4. Review process to prevent future misses

---

## Support

For questions or issues with this workflow:
1. Review this documentation
2. Check project-specific PRD structure
3. Consult with team lead or project manager
4. Update this workflow if improvements identified

---

**Last Updated**: 2026-03-25  
**Template Version**: 1.0.0  
**Maintained By**: Development Standards Team  
**License**: Copy freely to any project
