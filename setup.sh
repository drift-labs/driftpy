git submodule update --init --recursive
# build v2
cd protocol-v2
yarn && anchor build 
# build dependencies for v2
cd deps/serum-dex/dex && anchor build && cd ../../
# go back to top-level
cd ../