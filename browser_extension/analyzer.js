// 信息熵猜测算法的JS实现，逻辑对应src/caice.py的CSPlayerAnalyzer
class CSPlayerAnalyzer {
  constructor(allPlayers) {
    this.allPlayers = allPlayers;
    this.possiblePlayers = [...allPlayers];
    this.guessHistory = [];
    this.attributes = ["nationality", "team", "age", "majorAppearances", "role"];
  }

  reset() {
    this.possiblePlayers = [...this.allPlayers];
    this.guessHistory = [];
  }

  updatePossibilities(feedback) {
    this.possiblePlayers = this.possiblePlayers.filter((player) => {
      for (const key of Object.keys(feedback)) {
        const value = feedback[key];
        if (!value || typeof value !== "object" || !("result" in value)) continue;

        if (key === "team") {
          const teamName = value.data ? value.data.name : null;
          if (value.result === "CORRECT") {
            if (teamName === null) {
              if (player.team) return false;
            } else if (player.team !== teamName) {
              return false;
            }
          } else if (value.result === "INCORRECT") {
            if (teamName === null) {
              if (!player.team) return false;
            } else if (player.team === teamName) {
              return false;
            }
          }
        } else {
          const playerValue = player[key];
          const target = value.value;
          switch (value.result) {
            case "CORRECT":
              if (playerValue !== target) return false;
              break;
            case "INCORRECT":
            case "INCORRECT_CLOSE":
              if (playerValue === target) return false;
              break;
            case "HIGH_NOT_CLOSE":
              if (!(playerValue < target)) return false;
              break;
            case "LOW_NOT_CLOSE":
              if (!(playerValue > target)) return false;
              break;
            case "HIGH_CLOSE": {
              const margin = key === "age" ? 4 : 3;
              if (!(playerValue < target && playerValue > target - margin)) return false;
              break;
            }
            case "LOW_CLOSE": {
              const margin = key === "age" ? 4 : 3;
              if (!(playerValue > target && playerValue < target + margin)) return false;
              break;
            }
          }
        }
      }
      return true;
    });
    return this.possiblePlayers;
  }

  submitFeedback(feedback) {
    this.updatePossibilities(feedback);
    this.guessHistory.push(feedback.nickname);
  }

  calculateExpectedInformationGain(playerData) {
    if (this.possiblePlayers.length <= 1) return 0;

    let totalGain = 0;
    let totalWeight = 0;
    const n = this.possiblePlayers.length;
    const log2 = Math.log2;

    for (const attr of this.attributes) {
      const attrValue = playerData[attr];
      if (attrValue === null || attrValue === undefined) continue;

      if (attr === "age" || attr === "majorAppearances") {
        const margin = attr === "age" ? 3 : 2;
        let correctCount = 0, highNotCloseCount = 0, lowNotCloseCount = 0, highCloseCount = 0, lowCloseCount = 0;

        for (const p of this.possiblePlayers) {
          const v = p[attr];
          if (v === attrValue) correctCount++;
          else if (v < attrValue && v < attrValue - margin) highNotCloseCount++;
          else if (v > attrValue && v > attrValue + margin) lowNotCloseCount++;
          else if (v < attrValue && v >= attrValue - margin) highCloseCount++;
          else if (v > attrValue && v <= attrValue + margin) lowCloseCount++;
        }

        const counts = [correctCount, highNotCloseCount, lowNotCloseCount, highCloseCount, lowCloseCount];
        let feedbackEntropySum = 0;
        for (const count of counts) {
          if (count > 0) feedbackEntropySum += (count / n) * log2(count);
        }

        const weight = attr === "age" ? 0.8 : 1.0;
        totalGain += weight * (log2(n) - feedbackEntropySum);
        totalWeight += weight;
      } else {
        let correctCount;
        if (attr === "team") {
          correctCount = attrValue === null
            ? this.possiblePlayers.filter((p) => !p.team).length
            : this.possiblePlayers.filter((p) => p.team === attrValue).length;
        } else {
          correctCount = this.possiblePlayers.filter((p) => p[attr] === attrValue).length;
        }
        const incorrectCount = n - correctCount;

        if (correctCount > 0 && correctCount < n) {
          const weight = attr === "role" ? 1.2 : 1.0;
          const conditionalEntropy =
            (correctCount / n) * log2(correctCount) + (incorrectCount / n) * log2(incorrectCount);
          totalGain += weight * (log2(n) - conditionalEntropy);
          totalWeight += weight;
        }
      }
    }

    return totalWeight > 0 ? totalGain / totalWeight : 0;
  }

  chooseNextGuess() {
    if (this.possiblePlayers.length === 0) return null;
    if (this.possiblePlayers.length === 1) return this.possiblePlayers[0];

    if (this.guessHistory.length === 0) {
      const friberg = this.possiblePlayers.find((p) => p.nickname === "friberg");
      if (friberg) return friberg;
    }

    let bestPlayer = null;
    let bestGain = -Infinity;
    for (const player of this.possiblePlayers) {
      if (this.guessHistory.includes(player.nickname)) continue;
      const gain = this.calculateExpectedInformationGain(player);
      if (gain > bestGain) {
        bestGain = gain;
        bestPlayer = player;
      }
    }

    if (!bestPlayer) {
      return this.possiblePlayers.find((p) => !this.guessHistory.includes(p.nickname)) || null;
    }
    return bestPlayer;
  }
}
