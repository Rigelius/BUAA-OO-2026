import com.oocourse.spec2.main.VideoInterface;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class Video implements VideoInterface {
    private static class Comment {
        private final int id;
        private final String content;

        Comment(int id, String content) {
            this.id = id;
            this.content = content;
        }
    }

    private final int id;
    private final int uploaderId;
    private final String type;
    private int playCount;
    private int likes;
    private int forwardCount;
    private int coins;
    private final List<Comment> comments = new ArrayList<>();
    private final Set<Integer> commentIdSet = new HashSet<>();
    private final Set<String> cleanKeywords = new HashSet<>();

    public Video(int id, int uploaderId, String type) {
        this.id = id;
        this.uploaderId = uploaderId;
        this.type = type;
    }

    @Override
    public int getId() {
        return id;
    }

    @Override
    public int getUploaderId() {
        return uploaderId;
    }

    @Override
    public String getType() {
        return type;
    }

    @Override
    public int getPlayCount() {
        return playCount;
    }

    @Override
    public int getLikes() {
        return likes;
    }

    @Override
    public int getForwardCount() {
        return forwardCount;
    }

    @Override
    public int getCoins() {
        return coins;
    }

    @Override
    public double getHeat() {
        return playCount + likes * 1.5 + forwardCount * 2.0 + coins * 2.5;
    }

    @Override
    public boolean containsComment(int id) {
        return commentIdSet.contains(id);
    }

    @Override
    public boolean equals(Object obj) {
        if (!(obj instanceof VideoInterface)) {
            return false;
        }
        return ((VideoInterface) obj).getId() == id;
    }

    public void addPlayCount() {
        playCount++;
    }

    public void addLike() {
        likes++;
    }

    public void removeLike() {
        likes--;
    }

    public void addForwardCount() {
        forwardCount++;
    }

    public void addCoins(int amount) {
        coins += amount;
    }

    public void addComment(int commentId, String comment) {
        comments.add(new Comment(commentId, comment));
        commentIdSet.add(commentId);
        cleanKeywords.clear();
    }

    public int[] cleanSpamComments(String keyword) {
        if (cleanKeywords.contains(keyword)) {
            return new int[]{0, 0};
        }
        int removed = 0;
        int maxCount = 0;
        int keptSize = 0;
        for (int i = 0; i < comments.size(); i++) {
            Comment comment = comments.get(i);
            if (containsKeyword(comment.content, keyword)) {
                removed++;
                maxCount = Math.max(maxCount, countKeyword(comment.content, keyword));
                commentIdSet.remove(comment.id);
            } else {
                comments.set(keptSize, comment);
                keptSize++;
            }
        }
        if (removed == 0) {
            cleanKeywords.add(keyword);
            return new int[]{0, 0};
        }
        comments.subList(keptSize, comments.size()).clear();
        cleanKeywords.add(keyword);
        return new int[]{removed, maxCount};
    }

    private boolean containsKeyword(String comment, String keyword) {
        return keyword.isEmpty() || comment.contains(keyword);
    }

    private int countKeyword(String comment, String keyword) {
        if (keyword.isEmpty()) {
            return comment.length() + 1;
        }
        int count = 0;
        for (int i = 0; i + keyword.length() <= comment.length(); i++) {
            if (comment.startsWith(keyword, i)) {
                count++;
            }
        }
        return count;
    }

    public int[] getCommentIds() {
        int[] copy = new int[comments.size()];
        for (int i = 0; i < comments.size(); i++) {
            copy[i] = comments.get(i).id;
        }
        return copy;
    }

    public String[] getCommentContents() {
        String[] copy = new String[comments.size()];
        for (int i = 0; i < comments.size(); i++) {
            copy[i] = comments.get(i).content;
        }
        return copy;
    }
}
