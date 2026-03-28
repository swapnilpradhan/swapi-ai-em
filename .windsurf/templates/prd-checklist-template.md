# PRD Update Checklist

**STANDARDIZED TEMPLATE - Copy to any project's `.windsurf/PRD_CHECKLIST.md`**

Use this checklist for every significant code change or feature implementation.

---

## Setup Instructions

### 1. Copy This File
```bash
# Copy to your project root
cp prd-checklist-template.md {{PROJECT_ROOT}}/.windsurf/PRD_CHECKLIST.md
```

### 2. Update Project Path
Replace `{{PROJECT_ROOT}}` with your actual project path.

### 3. Customize Sections
Adjust section names to match your PRD structure.

---

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

---

## Pre-Commit Checklist

Before committing any code change:

- [ ] **Review**: Read relevant PRD sections
- [ ] **Assess**: Determine if PRD needs updates
- [ ] **Version**: Decide on version increment (MAJOR.MINOR.PATCH)
- [ ] **Update**: Modify affected PRD sections
- [ ] **Status**: Update status indicators (✅ ⚠️ 🔴)
- [ ] **Log**: Add entry to Change Log table
- [ ] **Notify**: Inform stakeholders of PRD updates

---

## Section-Specific Updates

### Features Changed?
Update these sections:
- [ ] Core Features & Requirements
- [ ] Technical Architecture (if applicable)
- [ ] Roadmap & Milestones
- [ ] Success Metrics (if new KPIs)

### Code Quality Changed?
Update these sections:
- [ ] Code Quality Standards
- [ ] Testing Requirements
- [ ] Success Metrics (test coverage, complexity)
- [ ] Release Criteria (if quality gates changed)

### Security Changed?
Update these sections:
- [ ] Security Posture Requirements
- [ ] Release Criteria (security gates)
- [ ] Success Metrics (vulnerability count)
- [ ] Roadmap (security milestones)

### Architecture Changed?
Update these sections:
- [ ] Technical Architecture (diagram, stack)
- [ ] Core Features (if capabilities changed)
- [ ] Performance Requirements (if targets changed)
- [ ] Release Criteria (if deployment changed)

### Performance Changed?
Update these sections:
- [ ] Performance Requirements
- [ ] Success Metrics (response times, throughput)
- [ ] Technical Architecture (if optimizations affect design)
- [ ] Release Criteria (if SLAs changed)

### Tests Added/Changed?
Update these sections:
- [ ] Testing Requirements (coverage targets)
- [ ] Success Metrics (current coverage %)
- [ ] Release Criteria (test gates)
- [ ] Code Quality Standards (if new standards)

---

## Version Increment Guide

| Change Type | Example | Version | Priority |
|-------------|---------|---------|----------|
| New core component | Added authentication service | MINOR | P0-P1 |
| Architecture change | Microservices → Serverless | MAJOR | P0 |
| Security fix | Added rate limiting | MINOR | P0-P1 |
| Bug fix in PRD | Fixed typo in requirement | PATCH | P2 |
| New requirement | Added GDPR compliance | MINOR | P0-P1 |
| Clarification | Clarified existing requirement | PATCH | P2 |
| Feature complete | Finished authentication | PATCH | P1 |
| Breaking change | Changed API structure | MAJOR | P0 |
| Performance optimization | Reduced latency by 50% | MINOR | P1 |
| Test coverage increase | 50% → 80% coverage | PATCH | P1 |
| Documentation update | Updated README | PATCH | P2 |
| Dependency update | Upgraded framework version | PATCH/MINOR | P1-P2 |

---

## Status Indicator Guide

Use these consistently throughout your PRD:

### ✅ Complete/Good
**When to use:**
- Feature is fully implemented and working
- Requirement is met
- Standard is being followed
- Tests are passing
- No action needed

**Examples:**
- ✅ Authentication implemented
- ✅ 80% test coverage achieved
- ✅ Security audit passed

### ⚠️ Partial/In Progress
**When to use:**
- Feature is partially implemented
- Requirement is partially met
- Standard is being adopted
- Work in progress
- Some tests failing

**Examples:**
- ⚠️ Authentication 70% complete
- ⚠️ 60% test coverage (target: 80%)
- ⚠️ Security fixes in progress

### 🔴 Critical/Not Started
**When to use:**
- Feature not started
- Critical gap exists
- Requirement not met
- Must fix before production
- Blocker identified

**Examples:**
- 🔴 Authentication not implemented
- 🔴 0% test coverage
- 🔴 Critical security vulnerability

---

## Priority Level Guide

### P0: Critical
**Characteristics:**
- Must fix before production
- Blocks release
- Security vulnerability
- Data loss risk
- System unavailable

**Examples:**
- No authentication
- SQL injection vulnerability
- Data corruption bug
- System crashes

**Action:** Fix immediately

### P1: High
**Characteristics:**
- Important for production
- Affects user experience
- Performance issue
- Should fix before release

**Examples:**
- Slow response times
- Missing error handling
- Incomplete logging
- Poor UX

**Action:** Fix before release

### P2: Medium
**Characteristics:**
- Nice to have
- Quality improvement
- Enhancement
- Can defer to next release

**Examples:**
- Code refactoring
- Documentation updates
- UI polish
- Additional features

**Action:** Schedule for future sprint

### P3: Low
**Characteristics:**
- Future consideration
- Minor improvement
- Optional feature
- Technical debt

**Examples:**
- Code cleanup
- Optimization opportunities
- Future features
- Nice-to-have improvements

**Action:** Backlog for future

---

## Change Log Format

### Standard Entry
```markdown
| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 2.1.0 | 2026-03-25 | Implemented authentication (SEC1), updated roadmap Q1 | Team Name |
```

### Best Practices

**Be Specific:**
- ❌ Bad: "Updated security section"
- ✅ Good: "Implemented rate limiting (SEC8), added CORS restrictions (SEC4)"

**Reference Sections:**
- ✅ "Fixed CQ2 complexity metrics"
- ✅ "Completed F1 multi-agent implementation"
- ✅ "Updated SEC1-SEC3 security requirements"

**Track Impact:**
- ✅ "Updated roadmap Q1 → Q2 for ChromaDB implementation"
- ✅ "Increased test coverage from 35% to 57%"
- ✅ "Reduced API response time from 3s to 1.5s"

**Link Related Work:**
- ✅ "Added authentication (SEC1) - see PR #123"
- ✅ "Fixed performance issue (P3) - commit abc123"

---

## Common Scenarios

### Scenario 1: Fixed a Bug
**Version:** PATCH (2.0.0 → 2.0.1)

**Checklist:**
- [ ] Update Code Quality Standards (if relevant)
- [ ] Update Testing Requirements (if test added)
- [ ] Update Success Metrics (if bug count tracked)
- [ ] Add change log entry

**Change Log Example:**
```markdown
| 2.0.1 | 2026-03-25 | Fixed memory leak in agent cleanup | Dev Team |
```

### Scenario 2: Added New Feature
**Version:** MINOR (2.0.0 → 2.1.0)

**Checklist:**
- [ ] Update Core Features & Requirements
- [ ] Update Technical Architecture (if new components)
- [ ] Update Roadmap & Milestones
- [ ] Update Success Metrics (if new KPIs)
- [ ] Add change log entry

**Change Log Example:**
```markdown
| 2.1.0 | 2026-03-25 | Implemented authentication (SEC1), added RBAC | Dev Team |
```

### Scenario 3: Major Refactor
**Version:** MAJOR (2.0.0 → 3.0.0)

**Checklist:**
- [ ] Update Technical Architecture
- [ ] Update Core Features (if capabilities changed)
- [ ] Update Performance Requirements
- [ ] Update Release Criteria
- [ ] Update multiple sections as needed
- [ ] Add detailed change log entry

**Change Log Example:**
```markdown
| 3.0.0 | 2026-03-25 | BREAKING: Migrated to microservices architecture | Dev Team |
```

### Scenario 4: Security Fix
**Version:** MINOR (2.0.0 → 2.1.0)

**Checklist:**
- [ ] Update Security Posture Requirements
- [ ] Update Release Criteria (if security gates changed)
- [ ] Update Success Metrics (vulnerability count)
- [ ] Update Roadmap (if milestone affected)
- [ ] Add change log entry

**Change Log Example:**
```markdown
| 2.1.0 | 2026-03-25 | Security: Implemented rate limiting (SEC8) | Security Team |
```

### Scenario 5: Test Coverage Improved
**Version:** PATCH (2.0.0 → 2.0.1)

**Checklist:**
- [ ] Update Testing Requirements (current coverage)
- [ ] Update Success Metrics (coverage %)
- [ ] Update Code Quality Standards (if threshold met)
- [ ] Add change log entry

**Change Log Example:**
```markdown
| 2.0.1 | 2026-03-26 | Increased test coverage to 57% - added A2A and MCP tests | QA Team |
```

---

## Automation Triggers

### Automatic PRD Review Triggers

Update PRD when you:

| Action | Trigger | Sections to Update | Version |
|--------|---------|-------------------|---------|
| Create new service/agent | New file in `/src/agents/` | Features, Architecture | MINOR |
| Add authentication | Security-related code | Security, Features | MINOR |
| Add tests | New test files | Testing, Metrics | PATCH |
| Update dependencies | `package.json` / `requirements.txt` | Architecture, Security | PATCH |
| Add API endpoint | New route/controller | Features, Security | MINOR |
| Optimize performance | Performance improvements | Performance, Metrics | MINOR |
| Fix bug | Bug fix commit | Quality, Testing | PATCH |
| Refactor architecture | Major code restructure | Architecture | MAJOR |
| Update documentation | README/docs changes | N/A (optional) | PATCH |
| Add monitoring | Observability code | Architecture, Metrics | MINOR |

---

## Monthly Review Checklist

Even without changes, review PRD monthly:

### Accuracy Check
- [ ] All status indicators (✅ ⚠️ 🔴) are accurate
- [ ] Feature statuses match implementation
- [ ] Metrics reflect current state
- [ ] No outdated requirements

### Timeline Check
- [ ] Roadmap dates are realistic
- [ ] Milestones are achievable
- [ ] Deadlines are current
- [ ] Priorities are correct

### Metrics Check
- [ ] Success metrics are being tracked
- [ ] KPIs are measurable
- [ ] Targets are realistic
- [ ] Progress is documented

### Standards Check
- [ ] Security requirements reflect current threats
- [ ] Code quality standards are being met
- [ ] Performance targets are current
- [ ] Testing requirements are adequate

### Documentation Check
- [ ] Version number is current
- [ ] Change log is complete
- [ ] No orphaned requirements
- [ ] Dependencies are up-to-date

---

## Quick Commands

### View PRD Information
```bash
# View current version
head -10 {{PROJECT_ROOT}}/PRD.md | grep "Version"

# View change log
tail -30 {{PROJECT_ROOT}}/PRD.md

# Count status indicators
grep -o "✅\|⚠️\|🔴" {{PROJECT_ROOT}}/PRD.md | sort | uniq -c

# Search for specific requirement
grep -n "SEC1\|CQ1\|F1" {{PROJECT_ROOT}}/PRD.md

# View roadmap
grep -A 20 "## Roadmap" {{PROJECT_ROOT}}/PRD.md

# Find all critical items
grep -B 2 "🔴" {{PROJECT_ROOT}}/PRD.md

# Find all P0 items
grep -B 2 "P0" {{PROJECT_ROOT}}/PRD.md
```

### PRD Health Check
```bash
# Count requirements by status
echo "Complete: $(grep -c '✅' {{PROJECT_ROOT}}/PRD.md)"
echo "In Progress: $(grep -c '⚠️' {{PROJECT_ROOT}}/PRD.md)"
echo "Critical: $(grep -c '🔴' {{PROJECT_ROOT}}/PRD.md)"

# List all P0 items
grep -n "P0" {{PROJECT_ROOT}}/PRD.md
```

---

## Integration with Git

### Recommended Workflow

```bash
# 1. Create feature branch
git checkout -b feature/new-feature

# 2. Make code changes
# ... implement feature ...

# 3. Run pre-commit checklist
# - Review PRD sections
# - Update as needed
# - Increment version
# - Add change log

# 4. Commit code and PRD together
git add src/ tests/ PRD.md
git commit -m "feat: Add new feature (PRD v2.1.0)"

# 5. Push and create PR
git push origin feature/new-feature
```

### Commit Message Format

```
<type>: <description> (PRD v<version>)

<type> options:
- feat: New feature (MINOR)
- fix: Bug fix (PATCH)
- refactor: Code refactor (PATCH/MINOR)
- perf: Performance improvement (MINOR)
- test: Test additions (PATCH)
- docs: Documentation (PATCH)
- security: Security fix (MINOR)
- breaking: Breaking change (MAJOR)

Examples:
- feat: Add authentication (PRD v2.1.0)
- fix: Resolve memory leak (PRD v2.0.1)
- breaking: Migrate to microservices (PRD v3.0.0)
```

---

## Troubleshooting

### PRD Out of Sync?
1. Run full review of all sections
2. Compare PRD with actual implementation
3. Update all status indicators
4. Increment version (PATCH for sync)
5. Add change log: "Synchronized PRD with implementation"

### Forgot to Update PRD?
1. Update immediately (better late than never)
2. Note in change log: "Retroactive update for [feature]"
3. Use current date for change log entry
4. Review process to prevent future misses

### Unsure About Version?
- **Changed behavior?** → MAJOR
- **Added feature?** → MINOR
- **Fixed/clarified?** → PATCH
- **Still unsure?** → Default to MINOR

### Conflicting Changes?
1. Review both changes
2. Merge updates logically
3. Increment version based on most significant change
4. Document both changes in change log

---

## Customization Guide

### Adapt to Your Project

**1. Section Names:**
Replace with your PRD structure:
```markdown
- Core Features → Your Features Section
- Security Posture → Your Security Section
- Code Quality → Your Quality Section
```

**2. Status Indicators:**
Add project-specific indicators:
```markdown
- 🟢 Verified/Tested
- 🟡 Under Review
- ⚫ Deprecated
- 🔵 Planned
```

**3. Priority Levels:**
Adjust to your process:
```markdown
- P0: Blocker
- P1: Critical
- P2: High
- P3: Medium
- P4: Low
- P5: Backlog
```

**4. Version Scheme:**
If using different versioning:
```markdown
# Date-based
Version: YYYY.MM.PATCH
Example: 2026.03.1

# Calendar versioning
Version: YY.MM.MICRO
Example: 26.03.1
```

---

## Best Practices Summary

### Do's ✅
- ✅ Update PRD with every significant change
- ✅ Be specific in change descriptions
- ✅ Keep status indicators current
- ✅ Increment version consistently
- ✅ Maintain complete change log
- ✅ Review monthly
- ✅ Commit PRD with code changes
- ✅ Use this checklist

### Don'ts ❌
- ❌ Skip PRD updates
- ❌ Use vague descriptions
- ❌ Delete change log entries
- ❌ Skip version increments
- ❌ Let PRD drift from reality
- ❌ Commit code without PRD update
- ❌ Ignore monthly reviews

---

**Remember**: The PRD is your project's source of truth. Keep it current, accurate, and aligned with reality.

---

**Template Version**: 1.0.0  
**Last Updated**: 2026-03-25  
**Maintained By**: Development Standards Team  
**License**: Copy freely to any project
