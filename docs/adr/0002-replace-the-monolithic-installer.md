# Replace the monolithic installer

Build a new spec-led installer beside the current monolith instead of incrementally refactoring the existing script. The old script remains behavioral evidence until the replacement passes automated checks and a real Fresh gameplay acceptance run; this costs temporary duplication but prevents hidden state coupling and historical branches from defining the new architecture.
