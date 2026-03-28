# PRD Maintenance Templates

**Standardized templates for maintaining Product Requirements Documents across projects**

---

## Overview

This directory contains standardized, project-agnostic templates for PRD maintenance workflows. These templates can be copied to any project to ensure consistent PRD management practices.

---

## Available Templates

### 1. PRD Workflow Template
**File**: `prd-workflow-template.md`

**Purpose**: Step-by-step workflow for reviewing and updating PRD

**Copy to**: `<PROJECT_ROOT>/.windsurf/workflows/prd-update.md`

**Features**:
- When to update PRD
- Version increment rules (MAJOR.MINOR.PATCH)
- Section update guidelines
- Change log management
- Example update flows
- Integration with Git workflow

### 2. PRD Checklist Template
**File**: `prd-checklist-template.md`

**Purpose**: Quick reference checklist for PRD updates

**Copy to**: `<PROJECT_ROOT>/.windsurf/PRD_CHECKLIST.md`

**Features**:
- Quick decision tree
- Pre-commit checklist
- Section-specific update guides
- Version increment guide
- Status indicator guide
- Common scenarios
- Automation triggers

---

## Quick Start

### Setup for New Project

```bash
# 1. Navigate to your project
cd /path/to/your/project

# 2. Create .windsurf directories if they don't exist
mkdir -p .windsurf/workflows

# 3. Copy templates
cp /path/to/templates/prd-workflow-template.md .windsurf/workflows/prd-update.md
cp /path/to/templates/prd-checklist-template.md .windsurf/PRD_CHECKLIST.md

# 4. Update project-specific paths
# Replace {{PROJECT_ROOT}} with your actual project path
sed -i '' 's|{{PROJECT_ROOT}}|/path/to/your/project|g' .windsurf/workflows/prd-update.md
sed -i '' 's|{{PROJECT_ROOT}}|/path/to/your/project|g' .windsurf/PRD_CHECKLIST.md

# 5. Customize for your project (optional)
# Edit section names, status indicators, priority levels, etc.
```

### macOS/Linux One-Liner

```bash
PROJECT_ROOT="/path/to/your/project" && \
mkdir -p "$PROJECT_ROOT/.windsurf/workflows" && \
cp prd-workflow-template.md "$PROJECT_ROOT/.windsurf/workflows/prd-update.md" && \
cp prd-checklist-template.md "$PROJECT_ROOT/.windsurf/PRD_CHECKLIST.md" && \
sed -i '' "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$PROJECT_ROOT/.windsurf/workflows/prd-update.md" && \
sed -i '' "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$PROJECT_ROOT/.windsurf/PRD_CHECKLIST.md" && \
echo "✅ PRD templates installed successfully!"
```

### Windows PowerShell

```powershell
$PROJECT_ROOT = "C:\path\to\your\project"
New-Item -ItemType Directory -Force -Path "$PROJECT_ROOT\.windsurf\workflows"
Copy-Item prd-workflow-template.md "$PROJECT_ROOT\.windsurf\workflows\prd-update.md"
Copy-Item prd-checklist-template.md "$PROJECT_ROOT\.windsurf\PRD_CHECKLIST.md"
(Get-Content "$PROJECT_ROOT\.windsurf\workflows\prd-update.md") -replace '{{PROJECT_ROOT}}', $PROJECT_ROOT | Set-Content "$PROJECT_ROOT\.windsurf\workflows\prd-update.md"
(Get-Content "$PROJECT_ROOT\.windsurf\PRD_CHECKLIST.md") -replace '{{PROJECT_ROOT}}', $PROJECT_ROOT | Set-Content "$PROJECT_ROOT\.windsurf\PRD_CHECKLIST.md"
Write-Host "✅ PRD templates installed successfully!"
```

---

## Customization

### Required Customizations

**1. Project Path**
Replace `{{PROJECT_ROOT}}` with your actual project path:
```bash
# Example
{{PROJECT_ROOT}} → /Users/admin/Git/my-project
```

### Optional Customizations

**2. PRD Section Names**
Adjust to match your PRD structure:
```markdown
# Default sections
- Core Features & Requirements
- Security Posture Requirements
- Code Quality Standards

# Your sections (example)
- Product Features
- Security Requirements
- Quality Standards
```

**3. Status Indicators**
Add project-specific indicators:
```markdown
# Default
- ✅ Complete/Good
- ⚠️ Partial/In Progress
- 🔴 Critical/Not Started

# Add custom
- 🟢 Verified/Tested
- 🟡 Under Review
- ⚫ Deprecated
```

**4. Priority Levels**
Adjust to your process:
```markdown
# Default
- P0: Critical
- P1: High
- P2: Medium

# Your levels (example)
- P0: Blocker
- P1: Critical
- P2: High
- P3: Medium
- P4: Low
```

**5. Version Scheme**
If using different versioning:
```markdown
# Default: Semantic Versioning
MAJOR.MINOR.PATCH (e.g., 2.1.0)

# Alternative: Date-based
YYYY.MM.PATCH (e.g., 2026.03.1)

# Alternative: Calendar Versioning
YY.MM.MICRO (e.g., 26.03.1)
```

---

## Integration with AI Assistants

### Cascade AI Memory Setup

To enable automatic PRD updates with Cascade AI:

```bash
# 1. Install templates (as shown above)

# 2. Create memory for automatic PRD review
# This is done through Cascade's create_memory tool with:
# - Title: "PRD Review and Versioning Workflow"
# - Content: Instructions for automatic PRD review
# - Tags: prd_workflow, documentation, versioning
```

**Memory Content Template**:
```
CRITICAL WORKFLOW: For every user request, I must:
1. Review PRD.md to check if changes affect project objectives, requirements, or specifications
2. Update relevant sections in PRD.md when:
   - New features are added or modified
   - Code quality standards change
   - Security requirements evolve
   - Technical architecture changes
   - Success metrics are affected
   - Release criteria are updated
3. Increment version number in PRD.md following semantic versioning (MAJOR.MINOR.PATCH)
4. Update the Change Log table at the bottom of PRD.md with date, changes, and author
5. Notify user of PRD updates made

Version increment rules:
- MAJOR (X.0.0): Breaking changes to architecture or core requirements
- MINOR (0.X.0): New features, significant requirement changes
- PATCH (0.0.X): Bug fixes, clarifications, minor updates

Current PRD version: [Your version]
Location: {{PROJECT_ROOT}}/PRD.md
```

### Manual Workflow Trigger

Use the workflow command:
```bash
/prd-update
```

---

## Template Maintenance

### Updating Templates

When you improve the workflow or checklist:

1. **Update the template files** in this directory
2. **Increment template version** in the footer
3. **Document changes** in template change log
4. **Notify teams** using the templates
5. **Provide migration guide** if breaking changes

### Template Versioning

Templates use their own versioning:
```markdown
**Template Version**: 1.0.0
**Last Updated**: YYYY-MM-DD
```

### Sharing Improvements

If you make improvements:
1. Update templates in this directory
2. Share with other teams/projects
3. Consider contributing back to standards repo
4. Document lessons learned

---

## Best Practices

### For Template Users

✅ **Do**:
- Copy templates to each new project
- Customize for project-specific needs
- Keep templates updated with improvements
- Share learnings with team

❌ **Don't**:
- Modify templates in place (copy first)
- Skip customization step
- Forget to update project paths
- Ignore template updates

### For Template Maintainers

✅ **Do**:
- Keep templates project-agnostic
- Use placeholders ({{PROJECT_ROOT}})
- Document all customization points
- Version templates independently
- Provide clear examples

❌ **Don't**:
- Hardcode project-specific values
- Make breaking changes without notice
- Skip documentation updates
- Forget backward compatibility

---

## Examples

### Example 1: Web Application Project

```bash
# Setup
PROJECT_ROOT="/Users/dev/projects/webapp"
mkdir -p "$PROJECT_ROOT/.windsurf/workflows"
cp prd-workflow-template.md "$PROJECT_ROOT/.windsurf/workflows/prd-update.md"
cp prd-checklist-template.md "$PROJECT_ROOT/.windsurf/PRD_CHECKLIST.md"

# Customize
sed -i '' "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$PROJECT_ROOT/.windsurf/workflows/prd-update.md"
sed -i '' "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$PROJECT_ROOT/.windsurf/PRD_CHECKLIST.md"

# Add custom sections for web app
# - Frontend Features
# - Backend API
# - Database Schema
# - Deployment Pipeline
```

### Example 2: Mobile App Project

```bash
# Setup
PROJECT_ROOT="/Users/dev/projects/mobile-app"
mkdir -p "$PROJECT_ROOT/.windsurf/workflows"
cp prd-workflow-template.md "$PROJECT_ROOT/.windsurf/workflows/prd-update.md"
cp prd-checklist-template.md "$PROJECT_ROOT/.windsurf/PRD_CHECKLIST.md"

# Customize
sed -i '' "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$PROJECT_ROOT/.windsurf/workflows/prd-update.md"
sed -i '' "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$PROJECT_ROOT/.windsurf/PRD_CHECKLIST.md"

# Add custom sections for mobile
# - iOS Features
# - Android Features
# - Cross-platform Components
# - App Store Requirements
```

### Example 3: Data Science Project

```bash
# Setup
PROJECT_ROOT="/Users/dev/projects/ml-model"
mkdir -p "$PROJECT_ROOT/.windsurf/workflows"
cp prd-workflow-template.md "$PROJECT_ROOT/.windsurf/workflows/prd-update.md"
cp prd-checklist-template.md "$PROJECT_ROOT/.windsurf/PRD_CHECKLIST.md"

# Customize
sed -i '' "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$PROJECT_ROOT/.windsurf/workflows/prd-update.md"
sed -i '' "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" "$PROJECT_ROOT/.windsurf/PRD_CHECKLIST.md"

# Add custom sections for ML
# - Model Architecture
# - Training Pipeline
# - Data Requirements
# - Model Performance Metrics
```

---

## Troubleshooting

### Templates Not Working?

**Issue**: Paths not resolving
- **Solution**: Verify `{{PROJECT_ROOT}}` was replaced correctly
- **Check**: `grep "{{PROJECT_ROOT}}" .windsurf/workflows/prd-update.md`

**Issue**: Workflow command not found
- **Solution**: Ensure file is in `.windsurf/workflows/` directory
- **Check**: `ls -la .windsurf/workflows/prd-update.md`

**Issue**: Customizations lost after update
- **Solution**: Keep project-specific customizations separate
- **Tip**: Document customizations in project README

### Getting Help

1. Review template documentation
2. Check examples in this README
3. Consult team lead or project manager
4. Review original implementation in reference project

---

## Contributing

### Improving Templates

If you discover improvements:

1. **Test thoroughly** in your project
2. **Document the change** clearly
3. **Update template version**
4. **Share with team**
5. **Consider contributing** to standards repo

### Feedback

Share feedback on:
- Missing features
- Unclear instructions
- Customization challenges
- Integration issues
- Best practices

---

## License

These templates are provided as-is for use in any project. Copy, modify, and distribute freely.

---

## Support

For questions or issues:
1. Review this documentation
2. Check template comments and examples
3. Consult project-specific PRD structure
4. Contact development standards team

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-03-25 | Initial template creation | Development Standards Team |

---

**Maintained By**: Development Standards Team  
**Last Updated**: 2026-03-25  
**Template Collection Version**: 1.0.0
