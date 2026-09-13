# Contributing to LoopCam

Hello, and welcome. If you are reading this, it means you are interested in making LoopCam better. We appreciate that. 

This project was built on a few core promises: minimal dependencies, a clean file structure, and code that reads like a conversation rather than a textbook. We don't use emojis in our commit messages or code comments. We prefer clear, human sentences.

## How to Contribute

1. **Fork and Clone**: Grab your own copy of the repository.
2. **Branching**: Create a branch with a descriptive name. Something like `feature/add-pip-support` or `fix/audio-latency-drift`.
3. **Write Code**: Keep it simple. If you need to use a complex workaround, explain why in a comment. Tell the next developer what you were thinking.
4. **Test**: Make sure your changes work on a standard Debian environment. We rely on `v4l2loopback` and `pulseaudio-utils`, so keep an eye on how your changes interact with them.
5. **Submit a PR**: Open a Pull Request. In your description, just talk to us. Tell us what you fixed, how you fixed it, and if there are any quirks we should know about.

## Code Style

- We use standard PEP 8, but we aren't robots. Readability beats strict adherence to arbitrary line-length rules if it makes the logic easier to follow.
- Use lowercase for comments. It feels a bit more relaxed and fits the minimalist aesthetic of the app.
- Avoid "AI slop". If you use an LLM to help you write a function, please rewrite it in your own words and add comments that reflect your actual understanding of the code. We want developers who know why the code works.

## Reporting Bugs

If LoopCam crashes or fails to route audio/video, open an issue. Please include:
- Your Debian/Ubuntu version.
- The output of `pactl info` and `v4l2-ctl --list-devices`.
- A simple description of what you were trying to do when it failed.

Thank you for helping keep LoopCam human.