#!/usr/bin/env sh
set -eu

LEA_RELEASE="v0.3.0"
LEA_WHEEL="lea_agent-0.3.0-py3-none-any.whl"
LEA_WHEEL_SHA256="3cbb85b6e7545c2129c30c681ea69e28b75a25591366438658a370fd779fd7c9"
LEA_WHEEL_URL="https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/releases/download/${LEA_RELEASE}/${LEA_WHEEL}"
UV_INSTALL_URL="https://astral.sh/uv/install.sh"

if [ "${LEA_INSTALL_DRY_RUN:-0}" = "1" ]; then
    echo "LEA installer dry run"
    echo "wheel: ${LEA_WHEEL_URL}"
    echo "sha256: ${LEA_WHEEL_SHA256}"
    if [ "${LEA_WITH_MCP:-0}" = "1" ]; then
        echo "install: uv tool install --python 3.12 --force --with mcp>=2.1,<3 ${LEA_WHEEL}"
    else
        echo "install: uv tool install --python 3.12 --force ${LEA_WHEEL}"
    fi
    exit 0
fi

find_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
    elif [ -x "${HOME}/.local/bin/uv" ]; then
        echo "${HOME}/.local/bin/uv"
    elif [ -x "${HOME}/.cargo/bin/uv" ]; then
        echo "${HOME}/.cargo/bin/uv"
    else
        return 1
    fi
}

download() {
    source_url="$1"
    destination="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf "$source_url" -o "$destination"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$destination" "$source_url"
    else
        echo "LEA installer needs curl or wget." >&2
        exit 1
    fi
}

temp_dir=$(mktemp -d 2>/dev/null || mktemp -d -t lea-install)
cleanup() {
    rm -f -- "${temp_dir}/install-uv.sh" "${temp_dir}/${LEA_WHEEL}"
    rmdir "$temp_dir" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM

if ! uv_bin=$(find_uv); then
    echo "uv not found; installing it from ${UV_INSTALL_URL}"
    uv_installer="${temp_dir}/install-uv.sh"
    download "$UV_INSTALL_URL" "$uv_installer"
    sh "$uv_installer"
    if ! uv_bin=$(find_uv); then
        echo "uv was installed but could not be located." >&2
        exit 1
    fi
fi

wheel_path="${temp_dir}/${LEA_WHEEL}"
echo "Downloading LEA ${LEA_RELEASE}"
download "$LEA_WHEEL_URL" "$wheel_path"

if command -v sha256sum >/dev/null 2>&1; then
    actual_hash=$(sha256sum "$wheel_path" | awk '{print $1}')
elif command -v shasum >/dev/null 2>&1; then
    actual_hash=$(shasum -a 256 "$wheel_path" | awk '{print $1}')
else
    echo "No SHA-256 utility found (sha256sum or shasum)." >&2
    exit 1
fi

if [ "$actual_hash" != "$LEA_WHEEL_SHA256" ]; then
    echo "LEA wheel checksum mismatch; refusing to install." >&2
    exit 1
fi

if [ "${LEA_WITH_MCP:-0}" = "1" ]; then
    "$uv_bin" tool install --python 3.12 --force --with "mcp>=2.1,<3" "$wheel_path"
else
    "$uv_bin" tool install --python 3.12 --force "$wheel_path"
fi

tool_bin=$("$uv_bin" tool dir --bin)
echo "LEA ${LEA_RELEASE} installed and verified."
if [ -x "${tool_bin}/lea" ]; then
    "${tool_bin}/lea" version
fi
case ":${PATH}:" in
    *":${tool_bin}:"*) ;;
    *) echo "Add ${tool_bin} to PATH, then open a new terminal." ;;
esac
echo "Next: cd to a project and run 'lea init', then 'lea'."
