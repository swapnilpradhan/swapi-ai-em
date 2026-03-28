# PRD Maintenance Guide

## Overview

This document explains how to maintain the Product Requirements Document (PRD.md) to ensure it stays aligned with project reality as development progresses.

---

## Automated PRD Review System

### Memory-Based Automation

I have created a **persistent memory** that triggers automatic PRD review for every user request. This ensures:

1. ✅ PRD is reviewed before and after every significant change
2. ✅ Relevant sections are updated when features/requirements change
3. ✅ Version numbers are incremented following semantic versioning
4. ✅ Change log is maintained with every update
5. ✅ You are notified of all PRD updates

### How It Works

```
User Request → Code Changes → PRD Review → Update PRD → Notify User
     ↓              ↓              ↓            ↓            ↓
  Analyze      Implement      Check        Version      Summary
  Impact       Changes        Alignment    Increment    of Updates
```

---

## Workflow Integration

### Option 1: Use the Workflow Command (Recommended)

You can trigger PRD review manually using:

```bash
/prd-update
```

This will:
- Review current PRD state
- Identify sections needing updates
- Guide version increment decision
- Update PRD sections
- Log changes

### Option 2: Automatic Review (Active)

The system automatically reviews PRD when:
- New features are implemented
- Code quality changes occur
- Security requirements evolve
- Architecture modifications happen
- Test coverage changes
- Performance targets are affected

---

## Versioning Strategy

### Semantic Versioning (MAJOR.MINOR.PATCH)

**Current Version**: 2.0.0

#### MAJOR Version (X.0.0)
Increment when making **breaking changes**:
- Complete architecture overhaul
- Fundamental shift in project objectives
- Major feature additions that change product direction
- Significant security model changes
- Breaking API changes

**Example**: Switching from single-agent to multi-agent architecture
```
2.0.0 → 3.0.0
```

#### MINOR Version (0.X.0)
Increment when adding **new features or significant changes**:
- New agent implementations
- New feature requirements
- Significant code quality standard additions
- New security requirements
- Architecture enhancements (non-breaking)
- New testing frameworks

**Example**: Implementing authentication system
```
2.0.0 → 2.1.0
```

#### PATCH Version (0.0.X)
Increment for **bug fixes and minor updates**:
- Clarifications in requirements
- Corrections to metrics
- Documentation improvements
- Status indicator updates
- Minor requirement adjustments

**Example**: Updating test coverage from 35% to 40%
```
2.0.0 → 2.0.1
```

---

## Update Triggers

### Automatic Update Triggers

The PRD will be automatically reviewed and updated when:

| Trigger | Affected Sections | Version Type |
|---------|------------------|--------------|
| New agent created | Features, Architecture, Roadmap | MINOR |
| Security fix implemented | Security Posture, Release Criteria | MINOR |
| Test coverage increased | Testing Requirements, Success Metrics | PATCH |
| Performance optimization | Performance Requirements | PATCH |
| New dependency added | Technical Architecture, Security | PATCH |
| API endpoint added | Features, Security | MINOR |
| Bug fix in code | Code Quality (if relevant) | PATCH |
| Architecture refactor | Technical Architecture | MAJOR/MINOR |

### Manual Review Triggers

Request a PRD review when:
- Starting a new development phase
- Before major releases
- Monthly (scheduled review)
- After completing a milestone
- When requirements become unclear

---

## Section Mapping

### What to Update When

#### When Features Change
**Update these sections:**
- Core Features & Requirements (F1-F12)
- Technical Architecture (if new components)
- Roadmap & Milestones (mark complete/in-progress)
- Success Metrics (if new KPIs)

#### When Code Quality Changes
**Update these sections:**
- Code Quality Standards (CQ1-CQ7)
- Testing Requirements
- Success Metrics (test coverage, complexity)
- Release Criteria (if quality gates change)

#### When Security Changes
**Update these sections:**
- Security Posture Requirements (SEC1-SEC8)
- Release Criteria (security gates)
- Success Metrics (vulnerability count)
- Roadmap (security milestones)

#### When Architecture Changes
**Update these sections:**
- Technical Architecture (diagram, stack)
- Core Features (if capabilities change)
- Performance Requirements (if targets change)
- Release Criteria (if deployment changes)

#### When Tests Change
**Update these sections:**
- Testing Requirements (coverage targets)
- Success Metrics (current coverage %)
- Release Criteria (test gates)
- Code Quality Standards (if new standards)

---

## Status Indicator System

Use these consistently throughout the PRD:

### ✅ Complete/Good
- Feature is fully implemented and working
- Requirement is met
- Standard is being followed
- No action needed

### ⚠️ Partial/In Progress
- Feature is partially implemented
- Requirement is partially met
- Standard is being adopted
- Work in progress

### 🔴 Critical/Not Started
- Feature not started
- Critical gap exists
- Requirement not met
- **Must fix before production**

### Priority Levels

- **P0**: Critical - Must fix before production
- **P1**: High - Important for production
- **P2**: Medium - Nice to have

---

## Change Log Management

### Format

Every PRD update must include a change log entry:

```markdown
| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 2.1.0 | 2026-03-25 | Implemented authentication (SEC1), updated roadmap Q1 | Cascade AI |
| 2.0.1 | 2026-03-24 | Updated test coverage metrics (35% → 40%) | Cascade AI |
| 2.0.0 | 2026-03-23 | Initial PRD creation with comprehensive requirements | Cascade AI |
```

### Best Practices

1. **Be Specific**: Don't just say "updated requirements"
   - ❌ Bad: "Updated security section"
   - ✅ Good: "Implemented rate limiting (SEC8), added CORS restrictions (SEC4)"

2. **Reference Sections**: Include section IDs
   - ✅ "Fixed CQ2 complexity metrics"
   - ✅ "Completed F1 multi-agent implementation"

3. **Track Impact**: Note what changed
   - ✅ "Updated roadmap Q1 → Q2 for ChromaDB implementation"

4. **Link Related Work**: Reference commits or PRs when applicable
   - ✅ "Added authentication (SEC1) - see commit abc123"

---

## Review Checklist

### Before Every Commit

- [ ] Did I add/modify/remove a feature?
- [ ] Did I change code quality standards?
- [ ] Did I affect security posture?
- [ ] Did I change architecture?
- [ ] Did I impact performance?
- [ ] Did I update tests?
- [ ] Did I change success metrics?
- [ ] Did I update release criteria?

**If ANY answer is YES** → Update PRD

### Monthly Review (Even Without Changes)

- [ ] All status indicators (✅ ⚠️ 🔴) are accurate
- [ ] Roadmap dates are realistic
- [ ] Success metrics are being tracked
- [ ] Security requirements reflect current threats
- [ ] Code quality standards are being met
- [ ] Version number is current
- [ ] Change log is complete
- [ ] No orphaned or outdated requirements

---

## Examples

### Example 1: Implementing Authentication

**Changes Made:**
- Added JWT authentication middleware
- Implemented user roles (admin, user, readonly)
- Added API key authentication

**PRD Updates:**
```
Version: 2.0.0 → 2.1.0 (MINOR - new feature)

Sections Updated:
- SEC1: Authentication & Authorization
  Status: 🔴 → ✅
  Added: JWT implementation, RBAC, API keys
  
- F1: Multi-Agent Content Generation
  Added: Authentication requirement for API access
  
- Roadmap Q1:
  [x] Implement authentication (marked complete)

Change Log:
| 2.1.0 | 2026-03-25 | Implemented authentication (SEC1), added RBAC and API keys | Cascade AI |
```

### Example 2: Increasing Test Coverage

**Changes Made:**
- Added 25 new unit tests
- Coverage increased from 35% to 57%

**PRD Updates:**
```
Version: 2.1.0 → 2.1.1 (PATCH - metric update)

Sections Updated:
- CQ1: Test Coverage
  Current Status: ~35% → ~57%
  Action Items: Updated progress
  
- Success Metrics:
  Test coverage: 35% → 57% (Target: 80%)

Change Log:
| 2.1.1 | 2026-03-26 | Increased test coverage to 57% - added A2A and MCP tests | Cascade AI |
```

### Example 3: Major Architecture Change

**Changes Made:**
- Replaced mock ChromaDB with real implementation
- Added vector indexing pipeline
- Implemented semantic search

**PRD Updates:**
```
Version: 2.1.1 → 3.0.0 (MAJOR - breaking change)

Sections Updated:
- F4: Vector Database RAG
  Status: 🔴 → ✅
  Removed: Mock implementation
  Added: Production ChromaDB with indexing
  
- Technical Architecture:
  Updated: Vector Database section
  Added: Indexing pipeline diagram
  
- Performance Requirements:
  P3: Database Query Performance
  Status: Not measured → < 100ms (measured)
  
- Roadmap Q2:
  [x] Real ChromaDB implementation (moved from Q2 to Q1)

Change Log:
| 3.0.0 | 2026-03-27 | BREAKING: Replaced mock ChromaDB with production implementation | Cascade AI |
```

---

## Tools and Commands

### Quick PRD Commands

```bash
# View current version
head -10 PRD.md | grep "Version"

# View change log
tail -30 PRD.md

# Count status indicators
grep -o "✅\|⚠️\|🔴" PRD.md | sort | uniq -c

# Search for specific requirement
grep -n "SEC1\|CQ1\|F1" PRD.md

# View roadmap
grep -A 10 "## Roadmap" PRD.md
```

### Workflow Commands

```bash
# Trigger PRD review workflow
/prd-update

# View PRD checklist
cat .windsurf/PRD_CHECKLIST.md

# View workflow documentation
cat .windsurf/workflows/prd-update.md
```

---

## Integration with Development

### Git Workflow

```bash
# 1. Make code changes
git add backend/app/agents/new_agent.py

# 2. Update PRD (automatic or manual)
# PRD.md is updated with version increment

# 3. Commit both together
git add PRD.md
git commit -m "feat: Add new agent (PRD v2.2.0)"

# 4. Push changes
git push
```

### CI/CD Integration (Future)

Potential automation:
- Pre-commit hook to check if PRD needs update
- CI check to verify PRD version incremented
- Automated PRD diff in PR descriptions
- PRD validation in CI pipeline

---

## Troubleshooting

### PRD Out of Sync?

If PRD doesn't match reality:

1. **Run full review**: `/prd-update`
2. **Check each section** against actual implementation
3. **Update status indicators** to reflect current state
4. **Increment version** (PATCH for sync updates)
5. **Add change log entry**: "Synchronized PRD with current implementation"

### Version Confusion?

If unsure which version to use:

- **Changed behavior?** → MAJOR
- **Added feature?** → MINOR
- **Fixed/clarified?** → PATCH
- **Still unsure?** → Ask user or default to MINOR

### Missing Updates?

If you realize PRD wasn't updated:

1. Update immediately (better late than never)
2. Note in change log: "Retroactive update for [feature]"
3. Use current date for change log entry

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

### Don'ts ❌

- ❌ Don't skip PRD updates "for later"
- ❌ Don't use vague change descriptions
- ❌ Don't delete old change log entries
- ❌ Don't skip version increments
- ❌ Don't commit code without updating PRD
- ❌ Don't let PRD drift from reality
- ❌ Don't forget to notify user of updates

---

## Summary

The PRD maintenance system ensures:

1. **Automatic Review**: Every request triggers PRD review
2. **Consistent Versioning**: Semantic versioning applied automatically
3. **Complete History**: Change log tracks all updates
4. **User Notification**: You're always informed of PRD changes
5. **Alignment**: PRD stays synchronized with code reality

**Key Files:**
- `/Users/admin/Git/swapi-ai-em/PRD.md` - The PRD itself
- `.windsurf/workflows/prd-update.md` - Update workflow
- `.windsurf/PRD_CHECKLIST.md` - Quick reference checklist
- `PRD_MAINTENANCE.md` - This guide

**Current Status:**
- ✅ Memory created for automatic PRD review
- ✅ Workflow documentation created
- ✅ Checklist created
- ✅ Maintenance guide created
- ✅ System is active and monitoring

---

**The PRD is now a living, automatically maintained document that evolves with your project.**
