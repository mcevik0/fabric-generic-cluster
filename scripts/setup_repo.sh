#!/bin/bash
################################################################################
# FABRIC Slice Management Framework - Repository Setup Script
################################################################################
#
# This script helps you set up and update your GitHub repository with
# the refactored FABRIC slice management framework.
#
# Usage:
#   ./setup_repo.sh [options]
#
# Options:
#   --init          Initialize new repository structure
#   --update        Update existing files from Claude artifacts
#   --commit        Commit changes with default message
#   --push          Push changes to remote
#   --all           Do everything (init, update, commit, push)
#   --help          Show this help message
#
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
DO_INIT=false
DO_UPDATE=false
DO_COMMIT=false
DO_PUSH=false

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_git() {
    if ! command -v git &> /dev/null; then
        print_error "Git is not installed. Please install git first."
        exit 1
    fi
}

check_git_repo() {
    if [ ! -d .git ]; then
        print_error "Not a git repository. Run 'git init' first or use --init option."
        exit 1
    fi
}

################################################################################
# Main Functions
################################################################################

init_repository() {
    print_header "Initializing Repository Structure"
    
    # Check if already a git repo
    if [ -d .git ]; then
        print_warning "Already a git repository. Skipping git init."
    else
        print_info "Initializing git repository..."
        git init
        print_success "Git repository initialized"
    fi
    
    # Create directory structure (minimal - you keep files in root)
    print_info "Creating directory structure..."
    
    mkdir -p docs
    mkdir -p examples
    mkdir -p .github/workflows
    
    print_success "Directory structure created"
    
    # Create .gitignore if it doesn't exist
    if [ ! -f .gitignore ]; then
        print_info "Creating .gitignore..."
        cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
PIPFILE.lock

# Virtual environments
venv/
ENV/
env/

# Jupyter Notebook
.ipynb_checkpoints
*.ipynb_checkpoints/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# FABRIC specific
*.bak
*.backup
.fabric/

# Logs
*.log

# Temporary files
tmp/
temp/
*.tmp

# Secrets (be careful!)
*_secret.yaml
*_private.yaml
credentials.json
EOF
        print_success ".gitignore created"
    else
        print_info ".gitignore already exists"
    fi
    
    # Create placeholder files
    touch docs/.gitkeep
    touch examples/.gitkeep
    
    print_success "Repository initialization complete"
}

update_files() {
    print_header "Updating Framework Files"
    
    print_warning "This function requires you to copy artifacts from Claude."
    print_info "Files that need to be updated:"
    echo ""
    echo "  Core Modules:"
    echo "    - slice_utils_models.py"
    echo "    - slice_deployment.py"
    echo "    - slice_network_config.py"
    echo "    - slice_ssh_setup.py"
    echo "    - slice_topology_viewer.py"
    echo "    - slice_utils_builder_compat.py"
    echo "    - tool_topology_summary_generator.py"
    echo ""
    echo "  Configuration:"
    echo "    - requirements.txt"
    echo "    - README.md"
    echo ""
    echo "  Notebooks (root directory):"
    echo "    - notebook-aux-setup-environment.ipynb"
    echo "    - notebook-1.ipynb"
    echo "    - notebook-aux-topology-summary-generator.ipynb"
    echo ""
    echo "  Tests (root directory):"
    echo "    - test_fpga_support.py"
    echo "    - test_migration.py"
    echo "    - test_summary_generator.py"
    echo ""
    echo "  Example Topologies (optional):"
    echo "    - _slice_topology.yaml"
    echo "    - _slice_topology_kolla_*.yaml"
    echo ""
    
    read -p "Have you copied all the files? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Update cancelled. Copy files and run again."
        exit 0
    fi
    
    # Verify critical files exist
    CRITICAL_FILES=(
        "slice_utils_models.py"
        "slice_deployment.py"
        "slice_network_config.py"
        "requirements.txt"
    )
    
    MISSING_FILES=()
    for file in "${CRITICAL_FILES[@]}"; do
        if [ ! -f "$file" ]; then
            MISSING_FILES+=("$file")
        fi
    done
    
    if [ ${#MISSING_FILES[@]} -gt 0 ]; then
        print_error "Missing critical files:"
        for file in "${MISSING_FILES[@]}"; do
            echo "  - $file"
        done
        exit 1
    fi
    
    print_success "All critical files present"
    
    # Make scripts executable
    if [ -f "tool_topology_summary_generator.py" ]; then
        chmod +x tool_topology_summary_generator.py
        print_success "Made tool_topology_summary_generator.py executable"
    fi
    
    print_success "File update complete"
}

commit_changes() {
    print_header "Committing Changes"
    
    check_git_repo
    
    # Check if there are changes to commit
    if git diff-index --quiet HEAD --; then
        print_warning "No changes to commit"
        return 0
    fi
    
    # Show status
    print_info "Git status:"
    git status --short
    echo ""
    
    # Ask for confirmation
    read -p "Commit these changes? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Commit cancelled"
        return 0
    fi
    
    # Ask for custom commit message
    echo ""
    print_info "Enter commit message (or press Enter for default):"
    read -r CUSTOM_MESSAGE
    
    if [ -z "$CUSTOM_MESSAGE" ]; then
        COMMIT_MESSAGE="feat: Update FABRIC slice management framework

- Add refactored modular architecture
- Implement Pydantic models for type safety
- Add multi-OS network configuration support
- Add FPGA device support
- Include comprehensive documentation
- Add test suite and examples"
    else
        COMMIT_MESSAGE="$CUSTOM_MESSAGE"
    fi
    
    # Stage all changes
    git add -A
    
    # Commit
    git commit -m "$COMMIT_MESSAGE"
    
    print_success "Changes committed"
    
    # Show commit info
    echo ""
    print_info "Latest commit:"
    git log -1 --oneline
}

push_changes() {
    print_header "Pushing Changes to Remote"
    
    check_git_repo
    
    # Check if remote exists
    if ! git remote | grep -q 'origin'; then
        print_error "No remote 'origin' configured."
        print_info "Add remote with: git remote add origin <url>"
        exit 1
    fi
    
    # Get current branch
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    
    print_info "Current branch: $BRANCH"
    print_info "Remote: $(git remote get-url origin)"
    echo ""
    
    # Confirm push
    read -p "Push to origin/$BRANCH? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Push cancelled"
        return 0
    fi
    
    # Push
    git push origin "$BRANCH"
    
    print_success "Changes pushed to remote"
}

show_help() {
    cat << EOF
FABRIC Slice Management Framework - Repository Setup Script

Usage:
    ./setup_repo.sh [options]

Options:
    --init          Initialize new repository structure
    --update        Update existing files (prompts for confirmation)
    --commit        Commit changes with default or custom message
    --push          Push changes to remote repository
    --all           Execute all steps (init, update, commit, push)
    --help          Show this help message

Examples:
    # Initialize new repository
    ./setup_repo.sh --init

    # Update files and commit
    ./setup_repo.sh --update --commit

    # Do everything
    ./setup_repo.sh --all

    # Just push existing commits
    ./setup_repo.sh --push

Notes:
    - Ensure you have copied all necessary files before using --update
    - The script will ask for confirmation before destructive operations
    - You can customize the commit message when prompted

EOF
}

################################################################################
# Main Script
################################################################################

main() {
    # Parse arguments
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --init)
                DO_INIT=true
                shift
                ;;
            --update)
                DO_UPDATE=true
                shift
                ;;
            --commit)
                DO_COMMIT=true
                shift
                ;;
            --push)
                DO_PUSH=true
                shift
                ;;
            --all)
                DO_INIT=true
                DO_UPDATE=true
                DO_COMMIT=true
                DO_PUSH=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo ""
                show_help
                exit 1
                ;;
        esac
    done
    
    # Check git is installed
    check_git
    
    # Execute requested operations
    echo ""
    print_header "FABRIC Slice Management Framework Setup"
    echo ""
    
    if [ "$DO_INIT" = true ]; then
        init_repository
        echo ""
    fi
    
    if [ "$DO_UPDATE" = true ]; then
        update_files
        echo ""
    fi
    
    if [ "$DO_COMMIT" = true ]; then
        commit_changes
        echo ""
    fi
    
    if [ "$DO_PUSH" = true ]; then
        push_changes
        echo ""
    fi
    
    print_success "Setup complete!"
    echo ""
    
    # Show next steps
    print_header "Next Steps"
    echo ""
    echo "1. Review the changes:"
    echo "   git status"
    echo "   git log"
    echo ""
    echo "2. Test the framework:"
    echo "   python test_fpga_support.py"
    echo "   python test_migration.py"
    echo "   jupyter notebook notebook-aux-setup-environment.ipynb"
    echo ""
    echo "3. Update documentation as needed"
    echo ""
    echo "4. Create a release:"
    echo "   git tag -a v1.0.0 -m 'Initial release'"
    echo "   git push origin v1.0.0"
    echo ""
}

# Run main function
main "$@"
