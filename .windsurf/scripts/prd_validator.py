#!/usr/bin/env python3
"""
PRD Validator Script
Enforces PRD updates and validates compliance
"""

import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path

class PRDValidator:
    def __init__(self, prd_path: str = "PRD.md"):
        self.prd_path = prd_path
        self.prd_content = ""
        self.errors = []
        self.warnings = []
        
    def load_prd(self) -> bool:
        """Load PRD content"""
        try:
            with open(self.prd_path, 'r', encoding='utf-8') as f:
                self.prd_content = f.read()
            return True
        except FileNotFoundError:
            self.errors.append(f"PRD file not found: {self.prd_path}")
            return False
    
    def validate_version_format(self) -> bool:
        """Validate version format (X.Y.Z)"""
        version_match = re.search(r'\*\*Version\*\*:\s*([0-9]+\.[0-9]+\.[0-9]+)', self.prd_content)
        if not version_match:
            self.errors.append("Invalid or missing version format. Expected: **Version**: X.Y.Z")
            return False
        
        version = version_match.group(1)
        print(f"✅ Version found: {version}")
        return True
    
    def validate_date_format(self) -> bool:
        """Validate last updated date"""
        date_match = re.search(r'\*\*Last Updated\*\*:\s*([A-Za-z]+\s+[0-9]+,\s*[0-9]+)', self.prd_content)
        if not date_match:
            self.errors.append("Invalid or missing last updated date")
            return False
        
        date_str = date_match.group(1)
        print(f"✅ Last updated: {date_str}")
        return True
    
    def validate_change_log(self) -> bool:
        """Validate change log structure"""
        # Check for change log section
        if "### Change Log" not in self.prd_content:
            self.errors.append("Change Log section not found")
            return False
        
        # Check for change log table
        table_pattern = r'\|\s*Version\s*\|\s*Date\s*\|\s*Changes\s*\|\s*Author\s*\|'
        if not re.search(table_pattern, self.prd_content):
            self.errors.append("Change Log table header not found")
            return False
        
        # Count change log entries
        entry_pattern = r'\|\s*([0-9]+\.[0-9]+\.[0-9]+)\s*\|[^|]+\|[^|]+\|[^|]+\|'
        entries = re.findall(entry_pattern, self.prd_content)
        
        if len(entries) < 2:
            self.warnings.append(f"Change log has only {len(entries)} entries (expected at least 2)")
        
        print(f"✅ Change log entries: {len(entries)}")
        return True
    
    def validate_required_sections(self) -> bool:
        """Validate required PRD sections"""
        required_sections = [
            "## Executive Summary",
            "## Vision & Objectives", 
            "## System Architecture",
            "## Technology Stack",
            "## Roadmap & Milestones",
            "### Change Log"
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in self.prd_content:
                missing_sections.append(section)
        
        if missing_sections:
            self.errors.append(f"Missing required sections: {', '.join(missing_sections)}")
            return False
        
        print(f"✅ All required sections present")
        return True
    
    def check_recent_updates(self) -> bool:
        """Check if PRD has been updated recently"""
        date_match = re.search(r'\*\*Last Updated\*\*:\s*([A-Za-z]+\s+([0-9]+),\s*([0-9]+))', self.prd_content)
        if not date_match:
            return False
        
        try:
            month_day = date_match.group(1)
            # Simple check - just verify it's current year
            year = int(date_match.group(3))
            current_year = datetime.now().year
            
            if year < current_year:
                self.warnings.append(f"PRD last updated in {year} (current year is {current_year})")
            elif year > current_year:
                self.errors.append(f"PRD last updated date is in the future: {year}")
            
            return True
        except ValueError:
            self.errors.append("Invalid date format in Last Updated field")
            return False
    
    def validate_roadmap_consistency(self) -> bool:
        """Check roadmap for consistency"""
        # Look for Q1 2026 section
        if "### Q1 2026" not in self.prd_content:
            self.warnings.append("Q1 2026 roadmap section not found")
            return False
        
        # Check for completed items
        completed_items = len(re.findall(r'- \[x\]', self.prd_content))
        pending_items = len(re.findall(r'- \[ \]', self.prd_content))
        
        print(f"✅ Roadmap: {completed_items} completed, {pending_items} pending")
        return True
    
    def validate_technology_stack(self) -> bool:
        """Validate technology stack section"""
        tech_section = re.search(r'## Technology Stack.*?(?=##|\Z)', self.prd_content, re.DOTALL)
        if not tech_section:
            self.errors.append("Technology Stack section not found")
            return False
        
        # Check for key technologies
        tech_content = tech_section.group(0)
        required_tech = ["FastAPI", "ChromaDB", "OpenAI", "Redis"]
        
        missing_tech = []
        for tech in required_tech:
            if tech not in tech_content:
                missing_tech.append(tech)
        
        if missing_tech:
            self.warnings.append(f"Technology stack missing key items: {', '.join(missing_tech)}")
        
        print(f"✅ Technology stack section present")
        return True
    
    def run_validation(self) -> bool:
        """Run all validation checks"""
        print("🔍 PRD Validation Started...")
        print("=" * 50)
        
        if not self.load_prd():
            return False
        
        # Run all validations
        validations = [
            self.validate_version_format,
            self.validate_date_format,
            self.validate_change_log,
            self.validate_required_sections,
            self.check_recent_updates,
            self.validate_roadmap_consistency,
            self.validate_technology_stack
        ]
        
        all_passed = True
        for validation in validations:
            try:
                result = validation()
                if not result:
                    all_passed = False
            except Exception as e:
                self.errors.append(f"Validation error: {str(e)}")
                all_passed = False
        
        # Print results
        print("=" * 50)
        
        if self.errors:
            print("❌ ERRORS FOUND:")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print("⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if all_passed and not self.warnings:
            print("✅ PRD validation PASSED!")
        elif all_passed:
            print("✅ PRD validation PASSED (with warnings)")
        else:
            print("❌ PRD validation FAILED!")
        
        return all_passed
    
    def suggest_updates(self, changed_files: list) -> list:
        """Suggest PRD updates based on changed files"""
        suggestions = []
        
        for file_path in changed_files:
            if 'agent' in file_path.lower():
                suggestions.append("Consider updating System Architecture section")
            
            if 'vector_db' in file_path.lower() or 'chroma' in file_path.lower():
                suggestions.append("Update Technology Stack - ChromaDB status")
                suggestions.append("Update Roadmap - vector database milestones")
            
            if 'auth' in file_path.lower() or 'security' in file_path.lower():
                suggestions.append("Update Security Requirements section")
                suggestions.append("Update Success Metrics - security KPIs")
            
            if 'test' in file_path.lower():
                suggestions.append("Update Testing Requirements section")
                suggestions.append("Update Roadmap - testing milestones")
        
        return list(set(suggestions))  # Remove duplicates

def main():
    """Main validation function"""
    validator = PRDValidator()
    
    # Check if specific files were provided
    if len(sys.argv) > 1:
        changed_files = sys.argv[1:]
        print(f"📝 Checking files: {', '.join(changed_files)}")
        
        suggestions = validator.suggest_updates(changed_files)
        if suggestions:
            print("\n💡 Suggested PRD Updates:")
            for suggestion in suggestions:
                print(f"  • {suggestion}")
    
    # Run validation
    success = validator.run_validation()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
