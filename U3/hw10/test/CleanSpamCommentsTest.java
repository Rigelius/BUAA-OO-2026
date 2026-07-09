import com.oocourse.spec2.exceptions.VideoIdNotFoundException;
import org.junit.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

public class CleanSpamCommentsTest {

    @Test
    public void testRemoveSpam() throws Exception {
        Network network = baseNetwork();
        network.sendComment(2, 101, 1, "prefix_spam");
        network.sendComment(2, 101, 2, "keep_one");
        network.sendComment(2, 101, 3, "spam_middle_spam");
        network.sendComment(2, 101, 4, "keep_two");
        network.sendComment(2, 101, 5, "suffix_spam");
        VideoSnapshot beforeTarget = new VideoSnapshot(video(network, 101));
        VideoSnapshot beforeOther = new VideoSnapshot(video(network, 102));

        int[] result = network.cleanSpamComments(101, "spam");

        assertArrayEquals(new int[]{3, 2}, result);
        assertNonCommentAttributes(beforeTarget, video(network, 101));
        assertVideoEquals(beforeOther, video(network, 102));
        assertComments(video(network, 101), new int[]{2, 4},
            new String[]{"keep_one", "keep_two"});
        assertFalse(video(network, 101).containsComment(1));
        assertTrue(video(network, 101).containsComment(2));
        assertFalse(video(network, 101).containsComment(3));
        assertTrue(video(network, 101).containsComment(4));
        assertFalse(video(network, 101).containsComment(5));
    }

    @Test
    public void testNoMatch() throws Exception {
        Network network = baseNetwork();
        network.sendComment(2, 101, 10, "alpha");
        network.sendComment(2, 101, 11, "beta");
        VideoSnapshot before = new VideoSnapshot(video(network, 101));

        int[] ids = video(network, 101).getCommentIds();
        String[] contents = video(network, 101).getCommentContents();
        ids[0] = -1;
        contents[0] = "mutated";
        assertVideoEquals(before, video(network, 101));

        int[] result = network.cleanSpamComments(101, "zzz");

        assertArrayEquals(new int[]{0, 0}, result);
        assertVideoEquals(before, video(network, 101));
    }

    @Test
    public void testOverlapCount() throws Exception {
        Network network = baseNetwork();
        network.sendComment(2, 101, 20, "aaaaa");
        network.sendComment(2, 101, 21, "baaab");
        network.sendComment(2, 101, 22, "xxaa");
        VideoSnapshot before = new VideoSnapshot(video(network, 101));

        int[] result = network.cleanSpamComments(101, "aa");

        assertArrayEquals(new int[]{3, 4}, result);
        assertNonCommentAttributes(before, video(network, 101));
        assertComments(video(network, 101), new int[0], new String[0]);
        assertFalse(video(network, 101).containsComment(20));
        assertFalse(video(network, 101).containsComment(21));
        assertFalse(video(network, 101).containsComment(22));
    }

    @Test
    public void testOnlyTargetVideo() throws Exception {
        Network network = baseNetwork();
        network.sendComment(2, 101, 40, "delete");
        network.sendComment(2, 101, 41, "keep");
        network.sendComment(2, 102, 42, "delete");
        network.sendComment(2, 102, 43, "keep_other");
        VideoSnapshot beforeOther = new VideoSnapshot(video(network, 102));

        int[] result = network.cleanSpamComments(101, "delete");

        assertArrayEquals(new int[]{1, 1}, result);
        assertComments(video(network, 101), new int[]{41}, new String[]{"keep"});
        assertVideoEquals(beforeOther, video(network, 102));
    }

    @Test
    public void testMissingVideo()
        throws Exception {
        Network network = baseNetwork();
        network.sendComment(2, 101, 50, "spam");
        network.sendComment(2, 102, 51, "spam");
        VideoSnapshot before101 = new VideoSnapshot(video(network, 101));
        VideoSnapshot before102 = new VideoSnapshot(video(network, 102));

        try {
            network.cleanSpamComments(404, "spam");
            fail("Expected VideoIdNotFoundException");
        } catch (VideoIdNotFoundException e) {
            assertVideoEquals(before101, video(network, 101));
            assertVideoEquals(before102, video(network, 102));
        }
    }

    private static Network baseNetwork() throws Exception {
        Network network = new Network();
        network.addUser(1, "Up", 20);
        network.addUser(2, "Viewer", 22);
        network.addUser(3, "OtherViewer", 24);
        network.addUser(4, "Follower", 26);
        network.followUser(4, 2);
        network.addUserCoins(2, 10);
        network.addUserCoins(3, 10);
        network.uploadVideo(1, 101, "tech");
        network.uploadVideo(1, 102, "music");
        network.watchVideo(2, 101);
        network.watchVideo(3, 102);
        network.likeVideo(2, 101);
        network.coinVideo(2, 101, 2);
        network.forwardVideo(2, 101, 4);
        return network;
    }

    private static Video video(Network network, int id) {
        Video video = (Video) network.getVideo(id);
        assertNotNull(video);
        return video;
    }

    private static void assertNonCommentAttributes(VideoSnapshot expected, Video actual) {
        assertEquals(expected.id, actual.getId());
        assertEquals(expected.uploaderId, actual.getUploaderId());
        assertEquals(expected.type, actual.getType());
        assertEquals(expected.playCount, actual.getPlayCount());
        assertEquals(expected.likes, actual.getLikes());
        assertEquals(expected.forwardCount, actual.getForwardCount());
        assertEquals(expected.coins, actual.getCoins());
        assertEquals(expected.heat, actual.getHeat(), 0.0);
    }

    private static void assertVideoEquals(VideoSnapshot expected, Video actual) {
        assertNonCommentAttributes(expected, actual);
        assertComments(actual, expected.commentIds, expected.commentContents);
        for (int id : expected.commentIds) {
            assertTrue(actual.containsComment(id));
        }
        for (int id : actual.getCommentIds()) {
            assertTrue(contains(expected.commentIds, id));
        }
    }

    private static boolean contains(int[] array, int target) {
        for (int value : array) {
            if (value == target) {
                return true;
            }
        }
        return false;
    }

    private static void assertComments(Video actual, int[] expectedIds,
                                       String[] expectedContents) {
        int[] actualIds = actual.getCommentIds();
        String[] actualContents = actual.getCommentContents();
        assertEquals(expectedIds.length, actualIds.length);
        assertEquals(expectedContents.length, actualContents.length);
        assertEquals(actualIds.length, actualContents.length);
        Map<Integer, String> expected = toCommentMap(expectedIds, expectedContents);
        Map<Integer, String> actualMap = toCommentMap(actualIds, actualContents);
        assertEquals(expected, actualMap);
    }

    private static Map<Integer, String> toCommentMap(int[] ids, String[] contents) {
        assertEquals(ids.length, contents.length);
        Map<Integer, String> result = new HashMap<>();
        for (int i = 0; i < ids.length; i++) {
            assertFalse(result.containsKey(ids[i]));
            result.put(ids[i], contents[i]);
        }
        return result;
    }

    private static class VideoSnapshot {
        private final int id;
        private final int uploaderId;
        private final String type;
        private final int playCount;
        private final int likes;
        private final int forwardCount;
        private final int coins;
        private final double heat;
        private final int[] commentIds;
        private final String[] commentContents;

        VideoSnapshot(Video video) {
            this.id = video.getId();
            this.uploaderId = video.getUploaderId();
            this.type = video.getType();
            this.playCount = video.getPlayCount();
            this.likes = video.getLikes();
            this.forwardCount = video.getForwardCount();
            this.coins = video.getCoins();
            this.heat = video.getHeat();
            this.commentIds = video.getCommentIds();
            this.commentContents = video.getCommentContents();
        }
    }
}
