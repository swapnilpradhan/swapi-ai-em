# PRD Update Checklist

Use this checklist for every significant code change or feature implementation.

## Quick Decision Tree

```
Did you make a code change?
  └─> YES
      └─> Does it affect any of these?
          ├─> Features (add/modify/remove) ────────────> Update PRD ✓
          ├─> Code quality standards ─────────────────> Update PRD ✓
          ├─> Security requirements ──────────────────> Update PRD ✓
          ├─> Architecture ───────────────────────────> Update PRD ✓
          ├─> Performance targets ────────────────────> Update PRD ✓
          ├─> Testing requirements ───────────────────> Update PRD ✓
          ├─> Success metrics ────────────────────────> Update PRD ✓
          ├─> Release criteria ───────────────────────> Update PRD ✓
          └─> Roadmap milestones ─────────────────────> Update PRD ✓
```

## Pre-Commit Checklist

Before committing any code change:

- [ ] **Review**: Read relevant PRD sections
- [ ] **Assess**: Determine if PRD needs updates
- [ ] **Version**: Decide on version increment (MAJOR.MINOR.PATCH)
- [ ] **Update**: Modify affected PRD sections
- [ ] **Status**: Update status indicators (✅ ⚠️ 🔴)
- [ ] **Log**: Add entry to Change Log table
- [ ] **Notify**: Inform user of PRD updates

## Section-Specific Updates

### Features Changed?
Update these sections:
- [ ] Core Features & Requirements (F1-F12)
- [ ] Technical Architecture (if applicable)
- [ ] Roadmap & Milestones

### Code Quality Changed?
Update these sections:
- [ ] Code Quality Standards (CQ1-CQ7)
- [ ] Testing Requirements
- [ ] Success Metrics (test coverage)

### Security Changed?
Update these sections:
- [ ] Security Posture Requirements (SEC1-SEC8)
- [ ] Release Criteria
- [ ] Success Metrics (vulnerabilities)

### Performance Changed?
Update these sections:
- [ ] Performance Requirements (P1-P6)
- [ ] Success Metrics (response times)
- [ ] Technical Architecture

### Tests Added?
Update these sections:
- [ ] Testing Requirements
- [ ] Success Metrics (coverage %)
- [ ] Release Criteria

## Version Increment Guide

| Change Type | Example | Version |
|-------------|---------|---------|
| New core agent | Added authentication agent | MINOR |
| Architecture change | Switched from mock to real ChromaDB | MAJOR |
| Security fix | Added rate limiting | MINOR |
| Bug fix in PRD | Fixed typo in requirement | PATCH |
| New requirement | Added GDPR compliance | MINOR |
| Clarification | Clarified existing requirement | PATCH |
| Feature complete | Finished authentication | PATCH |
| Breaking change | Changed API structure | MAJOR |

## Status Indicator Guide

Use these consistently:

- **✅ Complete/Good**: Feature implemented and working, requirement met
- **⚠️ Partial/In Progress**: Feature partially implemented, requirement partially met
- **🔴 Critical/Not Started**: Feature not started, critical gap, must fix

## Change Log Format

```markdown
| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 2.1.0 | 2026-03-25 | Added authentication (SEC1), updated roadmap | Cascade AI |
```

## Common Scenarios

### Scenario 1: Fixed a Bug
- **Version**: PATCH (2.0.0 → 2.0.1)
- **Update**: Code Quality Standards (if relevant)
- **Change Log**: "Fixed [bug description]"

### Scenario 2: Added New Feature
- **Version**: MINOR (2.0.0 → 2.1.0)
- **Update**: Core Features, Roadmap, possibly Architecture
- **Change Log**: "Implemented [feature name]"

### Scenario 3: Major Refactor
- **Version**: MAJOR (2.0.0 → 3.0.0)
- **Update**: Technical Architecture, possibly multiple sections
- **Change Log**: "Major refactor: [description]"

### Scenario 4: Security Fix
- **Version**: MINOR (2.0.0 → 2.1.0)
- **Update**: Security Posture Requirements, Release Criteria
- **Change Log**: "Security: [fix description]"

### Scenario 5: Test Coverage Improved
- **Version**: PATCH (2.0.0 → 2.0.1)
- **Update**: Testing Requirements, Success Metrics
- **Change Log**: "Increased test coverage to X%"

## Automation Triggers

Automatically update PRD when:

1. **New file created** in `/backend/app/agents/` → Check if new agent
2. **Security-related change** (auth, validation, encryption) → Update SEC sections
3. **Test file added** → Update testing metrics
4. **Dependencies changed** in `pyproject.toml` → Review security/architecture
5. **API endpoint added/modified** → Update features and security
6. **Performance optimization** → Update performance requirements

## Monthly Review

Even without changes, review monthly:

- [ ] All status indicators accurate?
- [ ] Roadmap dates realistic?
- [ ] Success metrics being tracked?
- [ ] Security requirements current?
- [ ] Code quality standards met?
- [ ] Version number current?
- [ ] Change log complete?

## Quick Commands

```bash
# View current PRD version
head -10 /Users/admin/Git/swapi-ai-em/PRD.md | grep "Version"

# View recent changes
tail -20 /Users/admin/Git/swapi-ai-em/PRD.md

# Search for specific requirement
grep -n "SEC1" /Users/admin/Git/swapi-ai-em/PRD.md

# Count status indicators
grep -o "✅\|⚠️\|🔴" /Users/admin/Git/swapi-ai-em/PRD.md | sort | uniq -c
```

---

**Remember**: The PRD is a living document. Keep it current, accurate, and aligned with reality.
