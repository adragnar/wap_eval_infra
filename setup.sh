echo "Setting up new Python project..."
rm -rf .git       # Remove template git history first
git init          # Initialize new repo
uv sync
git add .
git commit -m "Initial Commit"
echo "✅ Virtual environment created and dependencies installed!"
echo "TODO: add .env file with api keys locally"
