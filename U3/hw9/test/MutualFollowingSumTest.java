import com.oocourse.spec1.main.UserInterface;
import com.oocourse.spec1.main.VideoInterface;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.Parameterized;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Random;

import static org.junit.Assert.*;

@RunWith(Parameterized.class)
public class MutualFollowingSumTest {

    private final int caseId;

    public MutualFollowingSumTest(int caseId) {
        this.caseId = caseId;
    }

    @Parameterized.Parameters
    public static Collection<Object[]> prepareData() {
        List<Object[]> data = new ArrayList<>();
        for (int i = 0; i < 44; i++) {
            data.add(new Object[]{i});
        }
        return data;
    }

    @Test
    public void testQueryMutualFollowingSumSpec() throws Exception {
        NetworkCase actualCase = buildCase(caseId);
        NetworkCase expectedCase = buildCase(caseId);
        Network network = actualCase.network;
        Network compare = expectedCase.network;

        int expected = calculateMutualFollowingSum(compare);
        int actual = network.queryMutualFollowingSum();

        assertEquals(expected, actual);
        assertNetworkPure(network, compare, actualCase.videoIds);
        assertEquals(expected, network.queryMutualFollowingSum());
    }

    private static NetworkCase buildCase(int id) throws Exception {
        if (id == 0) {
            return new NetworkCase(new Network(), new int[0]);
        } else if (id == 1) {
            return buildOneUserCase();
        } else if (id == 2) {
            return buildTwoUserCase(false);
        } else if (id == 3) {
            return buildTwoUserCase(true);
        } else if (id == 4) {
            return buildMutualPairCase();
        } else if (id == 5) {
            return buildVideoSideEffectCase();
        } else if (id == 6) {
            return buildSmallCompleteVideoCase();
        } else if (id == 7) {
            return new NetworkCase(buildGraphByMode(20, 0), new int[0]);
        } else if (id == 8) {
            return new NetworkCase(buildGraphByMode(20, 1), new int[0]);
        } else if (id == 9) {
            return new NetworkCase(buildGraphByMode(30, 2), new int[0]);
        } else if (id < 20) {
            return buildRandomNetwork(new Random(42 + id), id - 5, id * 1000);
        } else {
            return buildWideRandomCase(97 + (id - 20) * 37);
        }
    }

    private static NetworkCase buildOneUserCase() throws Exception {
        Network net = new Network();
        net.addUser(1, "A", 20);
        return new NetworkCase(net, new int[0]);
    }

    private static NetworkCase buildTwoUserCase(boolean oneWay) throws Exception {
        Network net = new Network();
        net.addUser(1, "A", 20);
        net.addUser(2, "B", 21);
        if (oneWay) {
            net.followUser(1, 2);
        }
        return new NetworkCase(net, new int[0]);
    }

    private static NetworkCase buildMutualPairCase() throws Exception {
        Network net = new Network();
        net.addUser(1, "A", 20);
        net.addUser(2, "B", 21);
        net.followUser(1, 2);
        net.followUser(2, 1);
        return new NetworkCase(net, new int[0]);
    }

    private static NetworkCase buildVideoSideEffectCase() throws Exception {
        Network net = new Network();
        net.addUser(1, "A", 20);
        net.addUser(2, "B", 21);
        net.addUser(3, "C", 31);
        net.addUser(4, "D", 46);
        net.followUser(1, 2);
        net.followUser(2, 1);
        net.followUser(3, 1);
        net.followUser(4, 1);
        net.uploadVideo(1, 101);
        net.uploadVideo(1, 102);
        net.uploadVideo(2, 201);
        net.watchVideo(3, 101);
        return new NetworkCase(net, new int[]{101, 102, 201});
    }

    private static NetworkCase buildSmallCompleteVideoCase() throws Exception {
        Network net = new Network();
        for (int i = 1; i <= 5; i++) {
            net.addUser(i, "U" + i, 20 + i);
        }
        for (int i = 1; i <= 5; i++) {
            for (int j = 1; j <= 5; j++) {
                if (i != j) {
                    net.followUser(i, j);
                }
            }
        }
        net.uploadVideo(3, 301);
        return new NetworkCase(net, new int[]{301});
    }

    private static Network buildGraphByMode(int userCount, int mode)
        throws Exception {
        Network net = new Network();
        addSequentialUsers(net, userCount, "User", 20 + 5 * mode);
        if (mode == 1) {
            int[][] edges = new int[userCount][2];
            for (int i = 0; i < userCount; i++) {
                edges[i][0] = i;
                edges[i][1] = (i + 1) % userCount;
            }
            addEdges(net, edges);
        } else if (mode == 2) {
            for (int from = 0; from < userCount; from++) {
                for (int to = 0; to < userCount; to++) {
                    if (from != to) {
                        net.followUser(from, to);
                    }
                }
            }
        }
        return net;
    }

    private static void addSequentialUsers(Network net, int userCount,
                                           String prefix, int age)
        throws Exception {
        for (int id = 0; id < userCount; id++) {
            net.addUser(id, prefix + id, age);
        }
    }

    private static void addEdges(Network net, int[][] edges) throws Exception {
        for (int[] edge : edges) {
            net.followUser(edge[0], edge[1]);
        }
    }

    private static NetworkCase buildRandomNetwork(Random random, int userCount,
                                                  int videoIdOffset) throws Exception {
        Network net = new Network();
        List<Integer> uploadedVideoIds = new ArrayList<>();
        for (int i = 1; i <= userCount; i++) {
            net.addUser(i, "u" + i, 10 + random.nextInt(60));
        }
        for (int i = 1; i <= userCount; i++) {
            for (int j = 1; j <= userCount; j++) {
                if (i != j) {
                    double p = random.nextDouble();
                    if (p < 0.2) {
                        if (!net.getUser(i).isFollowing(net.getUser(j))) {
                            net.followUser(i, j);
                        }
                    } else if (p < 0.35) {
                        if (!net.getUser(i).isFollowing(net.getUser(j))) {
                            net.followUser(i, j);
                        }
                        if (!net.getUser(j).isFollowing(net.getUser(i))) {
                            net.followUser(j, i);
                        }
                    }
                }
            }
        }
        int videoId = videoIdOffset + 1;
        for (int i = 1; i <= userCount; i++) {
            if (random.nextBoolean()) {
                net.uploadVideo(i, videoId++);
                uploadedVideoIds.add(videoId - 1);
            }
        }
        for (int i = 1; i <= userCount; i++) {
            List<Integer> unwatched = net.queryReceivedUnwatchedVideos(i);
            if (!unwatched.isEmpty() && random.nextBoolean()) {
                net.watchVideo(i, unwatched.get(0));
            }
        }
        return new NetworkCase(net, toArray(uploadedVideoIds));
    }

    private static NetworkCase buildWideRandomCase(int seed) throws Exception {
        Network net = new Network();
        List<Integer> uploadedVideoIds = new ArrayList<>();
        Random random = new Random(seed);
        int userCount = random.nextInt(28) + 7;
        for (int id = 0; id < userCount; id++) {
            net.addUser(id, "User" + id, random.nextInt(100) + 1);
        }
        int attempts = 20 + random.nextInt(220);
        for (int k = 0; k < attempts; k++) {
            int from = random.nextInt(userCount);
            int to = random.nextInt(userCount);
            if (from != to && !net.getUser(from).isFollowing(net.getUser(to))) {
                net.followUser(from, to);
            }
        }
        int videoCount = random.nextInt(12);
        for (int index = 0; index < videoCount; index++) {
            int videoId = 7000 + seed * 16 + index;
            net.uploadVideo(random.nextInt(userCount), videoId);
            uploadedVideoIds.add(videoId);
        }
        return new NetworkCase(net, toArray(uploadedVideoIds));
    }

    private static int[] toArray(List<Integer> values) {
        int[] result = new int[values.size()];
        for (int i = 0; i < values.size(); i++) {
            result[i] = values.get(i);
        }
        return result;
    }

    private static int calculateMutualFollowingSum(Network network) {
        UserInterface[] users = network.getUsers();
        int expected = 0;
        for (int i = 0; i < users.length; i++) {
            for (int j = i + 1; j < users.length; j++) {
                if (users[i].isFollowing(users[j])
                    && users[j].isFollowing(users[i])) {
                    expected++;
                }
            }
        }
        return expected;
    }

    private static void assertNetworkPure(Network network, Network compare,
                                          int[] videoIds) throws Exception {
        UserInterface[] expectedUsers = compare.getUsers();
        UserInterface[] actualUsers = network.getUsers();
        assertEquals(expectedUsers.length, actualUsers.length);
        for (UserInterface expectedUser : expectedUsers) {
            UserInterface actualUser = network.getUser(expectedUser.getId());
            assertNotNull(actualUser);
            assertTrue(((User) actualUser).strictEquals(expectedUser));
            assertUserObservableState(actualUser, expectedUser, expectedUsers);
            assertUserVideos(actualUser, expectedUser, network, compare, videoIds);
        }
    }

    private static void assertUserObservableState(UserInterface actualUser,
                                                  UserInterface expectedUser,
                                                  UserInterface[] allUsers) {
        assertEquals(expectedUser.getId(), actualUser.getId());
        assertEquals(expectedUser.getName(), actualUser.getName());
        assertEquals(expectedUser.getAge(), actualUser.getAge());
        assertArrayEquals(expectedUser.queryAgeRatio(),
            actualUser.queryAgeRatio(), 0.0);
        assertEquals(expectedUser.queryReceivedUnwatchedVideos(),
            actualUser.queryReceivedUnwatchedVideos());
        for (UserInterface user : allUsers) {
            assertEquals(expectedUser.isFollowing(user), actualUser.isFollowing(user));
            assertEquals(expectedUser.containsFollower(user),
                actualUser.containsFollower(user));
        }
    }

    private static void assertUserVideos(UserInterface actualUser,
                                         UserInterface expectedUser,
                                         Network network, Network compare,
                                         int[] videoIds) {
        for (int videoId : videoIds) {
            VideoInterface actualVideo = network.getVideo(videoId);
            VideoInterface expectedVideo = compare.getVideo(videoId);
            assertNotNull(actualVideo);
            assertNotNull(expectedVideo);
            assertSame(actualVideo, network.getVideo(videoId));
            assertEquals(expectedUser.hasReceivedVideo(expectedVideo),
                actualUser.hasReceivedVideo(actualVideo));
        }
    }

    private static class NetworkCase {
        private final Network network;
        private final int[] videoIds;

        NetworkCase(Network network, int[] videoIds) {
            this.network = network;
            this.videoIds = videoIds;
        }
    }
}
