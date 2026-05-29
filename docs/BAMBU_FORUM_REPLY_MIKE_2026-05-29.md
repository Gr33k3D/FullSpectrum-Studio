# Reply Draft

Hi Mike,

You are right to ask. I had a packaging/release naming mistake on GitHub:
the small Windows rebuild was published under a newer tag, but the release
title and download filenames still said v0.4.3. That made it confusing to find.

I have fixed the release workflow and am publishing a fresh package as:

https://github.com/Gr33k3D/FullSpectrum-Studio/releases/tag/v0.4.5-community-preview

For Windows, use either:

- FullSpectrum-Studio-Windows-Setup-v0.4.5.exe
- FullSpectrum-Studio-Windows-Portable-v0.4.5.zip

About the file in my screenshots: that was a private validation model I used
for testing the preview/validation screens, so it was not included in the
repository. I should have made that clearer. The release itself should work
with your own painted `.3mf` files; if one fails, please send the error message
or a small test file and I will check it against the converter.

Thanks for pointing this out.
