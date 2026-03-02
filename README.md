# ai-engineering-buildcamp-code
Code for AI Engineering Buildcamp

Available Aliases:
git fetch-upstreams - Fetches from both upstream repositories
git merge-upstreams - Merges both upstream/main and upstream-course/main into your current branch
Usage:
To sync and merge both repositories into main:
git checkout main                    # Make sure you're on maingit fetch-upstreams                  # Fetch latest from both reposgit merge-upstreams                  # Merge both into main
Or as a one-liner:
git checkout main && git fetch-upstreams && git merge-upstreams
The merge-upstreams alias will:
First merge upstream/main (from ai-bootcamp-codespace)
Then merge upstream-course/main (from ai-engineering-buildcamp-code)
If there are conflicts, Git will pause after the first merge so you can resolve them before continuing.