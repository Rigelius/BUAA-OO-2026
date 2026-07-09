package com.oocourse.spec3.exceptions;

import java.util.HashMap;

public class ErrorCount {
    private int count;
    private final HashMap<Integer, Integer> errorId;

    public ErrorCount() {
        count = 0;
        errorId = new HashMap<>();
    }

    public void putError(int id) {
        if (errorId.containsKey(id)) {
            errorId.replace(id, errorId.get(id) + 1);
        } else {
            errorId.put(id, 1);
        }
        count++;
    }

    public void putError(int id1, int id2) {
        if (errorId.containsKey(id1)) {
            errorId.replace(id1, errorId.get(id1) + 1);
        } else {
            errorId.put(id1, 1);
        }
        if (errorId.containsKey(id2)) {
            errorId.replace(id2, errorId.get(id2) + 1);
        } else {
            errorId.put(id2, 1);
        }
        count++;
    }

    public int getCount() {
        return count;
    }

    public int getIdCount(int id) {
        if (!errorId.containsKey(id)) {
            return 0;
        }
        return errorId.get(id);
    }
}
