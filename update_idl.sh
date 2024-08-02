git submodule update --remote --merge --recursive &&
cd protocol-v2/ && 
anchor build && 
cp target/idl/drift.json ../src/driftpy/idl/drift.json