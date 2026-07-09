import com.oocourse.library2.LibraryBookIsbn;

import java.util.HashMap;
import java.util.HashSet;

public class RatingOffice {
    private final HashMap<LibraryBookIsbn, Integer> scoreSums = new HashMap<>();
    private final HashMap<LibraryBookIsbn, Integer> scoreCounts = new HashMap<>();

    public void gradeBook(LibraryBookIsbn isbn, int score) {
        scoreSums.put(isbn, scoreSums.getOrDefault(isbn, 0) + score);
        scoreCounts.put(isbn, scoreCounts.getOrDefault(isbn, 0) + 1);
    }

    public int getAverageScore(LibraryBookIsbn isbn) {
        int count = scoreCounts.getOrDefault(isbn, 0);
        if (count == 0) {
            return 0;
        }
        return scoreSums.get(isbn) / count;
    }

    public boolean isTreasuredBook(LibraryBookIsbn isbn) {
        return getAverageScore(isbn) >= 4;
    }

    public HashSet<LibraryBookIsbn> getTreasuredIsbns() {
        HashSet<LibraryBookIsbn> result = new HashSet<>();
        for (LibraryBookIsbn isbn : scoreCounts.keySet()) {
            if (isTreasuredBook(isbn)) {
                result.add(isbn);
            }
        }
        return result;
    }
}
