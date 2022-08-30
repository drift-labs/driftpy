cd protocol-v2/ && 
anchor build && 
cp target/idl/* ../src/driftpy/idl/ && 
cd .. &&
python parse_idl.py