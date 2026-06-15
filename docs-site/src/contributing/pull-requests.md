# Pull Request Process

When you're ready to submit your changes, please follow this process to ensure a smooth review.

## 1. Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/). Your commit messages should be structured as follows:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

### Examples

```
feat(api): add parameter to control motion blur
fix(dispatcher): handle Redis connection timeout
docs: update deployment instructions
chore: bump dependency versions
```

## 2. Open the Pull Request

1. Push your branch to your fork
2. Go to the main OsuRenderApi repository and click "Compare & pull request"
3. Fill out the Pull Request template provided
4. If your PR addresses an open issue, link to it using `Fixes #123` or `Resolves #123`

## 3. CI Pipeline

When you open a PR, GitHub Actions will automatically run:

1. **Lint & Type Check**: Black, Ruff, Pyright
2. **Security Scan**: Trivy filesystem scan, pip-audit
3. **Container Scan**: Trivy image scan on the built Docker image
4. **Unit Tests**: Pytest with coverage reporting

**All CI checks must pass before a PR can be merged.**

If a check fails, review the logs, fix the issue locally, commit, and push again.

## 4. Code Review

A maintainer will review your PR. They may ask for changes or provide suggestions.

- Be open to feedback
- If you don't understand a comment, ask for clarification
- Once you've addressed the feedback, push the new commits to your branch
- Do not force-push (`git push -f`) unless requested, as it makes the review history harder to follow

## 5. Merging

Once approved and all CI checks pass, a maintainer will merge your PR. We typically use "Squash and merge" to keep the main branch history clean.
