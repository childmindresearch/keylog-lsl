# keylog-lsl pull request guidelines

Pull requests are welcome. A code of conduct applies to all spaces managed by
the keylog-lsl project, including issues and pull requests. See the
[Code of Conduct](CODE_OF_CONDUCT.md) for details.

When submitting a pull request, check the following:

1. **Unit tests**, **documentation**, and **code style** are in order. The
   [Python Tests workflow](.github/workflows/test.yaml) defines the current
   requirements. Run the local checks with:

   ```sh
   uv run pre-commit run --all-files
   uv run pytest
   ```

2. The contribution is licensed under the same [license](LICENSE) as the rest
   of the repository. If you did not write the code yourself, ensure its
   license is compatible and include the applicable license information or
   obtain permission to relicense it.
