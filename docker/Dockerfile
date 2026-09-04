# ---- Frontend build ----
FROM node:20-slim AS web
WORKDIR /src
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# ---- Backend build ----
# The distribution must be pinned to the same one as the runtime stage: rust:1-slim rolls
# with upstream (now trixie / glibc 2.41), the binary it produces then requires GLIBC_2.38,
# and bookworm only has 2.36. The image builds fine, and the container dies on start with
# "version `GLIBC_2.38' not found".
FROM rust:1-slim-bookworm AS build
WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends pkg-config && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml Cargo.lock ./
COPY crates/ crates/
COPY migrations/ migrations/
# docs_corpus.rs compiles the in-product docs into the binary with include_str!, so they are
# a source dependency of the backend, not just a frontend asset. Drop this line and cargo
# build fails outright with couldn't read.
COPY web/src/docs/ web/src/docs/
RUN cargo build --release -p utopia-server

# ---- Runtime ----
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /src/target/release/utopia-server /usr/local/bin/utopia-server
COPY --from=web /src/dist /app/web-dist
ENV UTOPIA_WEB_DIST=/app/web-dist
EXPOSE 1516
CMD ["utopia-server"]
