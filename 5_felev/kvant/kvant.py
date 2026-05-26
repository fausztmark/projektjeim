from qiskit import QuantumCircuit #importáljuk a megfelelő qiskit könyvtárat
qc = QuantumCircuit(3)            #létrehozunk egy QuantumCircuit példányt
qc.h(0)
qc.cx(0,1)
qc.cx(0,2)
<qiskit.circuit.instructionset.InstructionSet at 0x201b485aac0>
qc.draw("latex")
qc_x = QuantumCircuit(2,0)
qc_x.x(0)
qc_x.draw("mpl")
qc_x.data
[CircuitInstruction(operation=Instruction(name='x', num_qubits=1, num_clbits=0, params=[]), qubits=(Qubit(QuantumRegister(2, 'q'), 0),), clbits=())]
qc_x.data[0].operation.definition.draw('mpl')
qc_a = QuantumCircuit(3) #Első áramkör
qc_a.x(1) 
qc_b = QuantumCircuit(2, name="qc_b") #Második áramkör
qc_b.x(0)
qc_b.z(1)
combined = qc_a.compose(qc_b, qubits=[1, 2]) #Összekapcsolás 
combined.draw("mpl")
qc_a = QuantumCircuit(3)
#qc_a.x(1)
qc_b = QuantumCircuit(2, name="qc_b")
qc_b.x(0)
qc_b.z(1)
inst = qc_b.to_instruction()
#qc_a.append(inst, [1, 2])
qc_a.draw("mpl")
qc_a.decompose().draw("mpl")
gate = qc_b.to_gate().control()
# Mivel ez egy vezérelt kapu, ezért 3 indexet kell megadni.
qc_a.append(gate, [0, 1, 2])
qc_a.draw("mpl")
qc_a.decompose().draw("mpl")
from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit
q = QuantumRegister(2,'q') #kvantumbiteket tartalmazó regiszter létrehozása
c = ClassicalRegister(2,'c') #klasszikus biteket tartalmazó regiszter
qc = QuantumCircuit(q,c) #kvantumhálózat készítése a regiszterekból
from qiskit.quantum_info import Statevector
state1 = Statevector([0.6,0.8])
qc.initialize(state1,qubits=q[0], normalize=True)
<qiskit.circuit.instructionset.InstructionSet at 0x201b69a45b0>
qc.draw("mpl")
