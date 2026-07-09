package com.oocourse.spec2.main;

import com.oocourse.spec2.exceptions.*;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.util.List;
import java.util.Scanner;

public class Runner {
    
    private String[] commands;
    private NetworkInterface network;

    private final Constructor<? extends UserInterface> userConstructor;
    private final Constructor<? extends NetworkInterface> networkConstructor;
    private final Constructor<? extends VideoInterface> videoConstructor;
    
    private final Scanner scanner;

    public Runner(Class<? extends UserInterface> userClass,
                  Class<? extends NetworkInterface> networkClass,
                  Class<? extends VideoInterface> videoClass)
            throws NoSuchMethodException, SecurityException {

        userConstructor = userClass.getConstructor(
                int.class, String.class, int.class);

        networkConstructor = networkClass.getConstructor();

        videoConstructor = videoClass.getConstructor(int.class, int.class, String.class);
        scanner = new Scanner(System.in);
    }

    private String getCurrentCommandString() {
        if (commands == null) return "";
        return String.join(" ", commands);
    }
    
    public void run()
            throws InstantiationException, IllegalAccessException,
            IllegalArgumentException, InvocationTargetException {

        this.network = this.networkConstructor.newInstance();
        while (scanner.hasNextLine()) {
            String line = scanner.nextLine();
            if (line.isEmpty()) continue;
            String cmd = line.split("\\s+")[0];
            try {
                if (cmd.equals("send_comment")) {
                    commands = line.split("\\s+", 5);
                    sendComment();
                } else if (cmd.equals("clean_spam_comments")) {
                    commands = line.split(" ", 3);
                    cleanSpamComments();
                } else {
                    commands = line.split("\\s+");
                    switch (cmd) {
                        case "add_user":
                            addUser();
                            break;
                        case "upload_video":
                            uploadVideo();
                            break;
                        case "follow_user":
                            followUser();
                            break;
                        case "unfollow_user":
                            unfollowUser();
                            break;
                        case "watch_video":
                            watchVideo();
                            break;
                        case "query_received_unwatched_videos":
                            queryReceivedUnwatchedVideos();
                            break;
                        case "query_up_followers_age_ratio":
                            queryUpFollowersAgeRatio();
                            break;
                        case "query_mutual_following_sum":
                            queryMutualFollowingSum();
                            break;
                        case "query_shortest_path":
                            queryShortestPath();
                            break;
                        case "add_user_coins":
                            addUserCoins();
                            break;
                        case "like_video":
                            likeVideo();
                            break;
                        case "coin_video":
                            coinVideo();
                            break;
                        case "query_best_contributor":
                            queryBestContributor();
                            break;
                        case "forward_video":
                            forwardVideo();
                            break;
                        case "query_most_popular_video":
                            queryMostPopularVideo();
                            break;
                        case "purchase_medal":
                            purchaseMedal();
                            break;
                        case "queryLongestDecSeq":
                            queryLongestDecSeq();
                            break;
                        case "end":
                            return ;
                        default:
                            break;
                    }
                }
            } catch (Exception e) {
                if (e instanceof InvocationTargetException) {
                    Throwable target = ((InvocationTargetException) e).getTargetException();
                    if (target instanceof MyException) {
                        ((MyException) target).print();
                        if (target instanceof Exception) {
                            ErrorStatisticsHandler.logError((Exception) target, getCurrentCommandString());
                        }
                    } else {
                        target.printStackTrace();
                    }
                } else if (e instanceof MyException) {
                    ((MyException) e).print();
                    ErrorStatisticsHandler.logError(e, getCurrentCommandString());
                } else {
                    e.printStackTrace();
                }
            }
        }
        scanner.close();
    }

    private void addUser() {
        int id = Integer.parseInt(commands[1]);
        int age = Integer.parseInt(commands[2]);
        String name = commands[3];
        try {
            network.addUser(id, name, age);
        } catch (EqualUserIdException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (InvalidAgeException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void uploadVideo() {
        int uploaderId = Integer.parseInt(commands[1]);
        int videoId = Integer.parseInt(commands[2]);
        String type = commands[3];
        try {
            network.uploadVideo(uploaderId, videoId, type);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (EqualVideoIdException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (InvalidTypeException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void followUser() {
        int id1 = Integer.parseInt(commands[1]);
        int id2 = Integer.parseInt(commands[2]);
        try {
            network.followUser(id1, id2);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (SelfSubscriptionException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (DuplicateSubscriptionException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void unfollowUser() {
        int id1 = Integer.parseInt(commands[1]);
        int id2 = Integer.parseInt(commands[2]);
        try {
            network.unfollowUser(id1, id2);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (FollowLinkNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void watchVideo() {
        int userId = Integer.parseInt(commands[1]);
        int videoId = Integer.parseInt(commands[2]);
        try {
            network.watchVideo(userId, videoId);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void queryReceivedUnwatchedVideos() {
        int userId = Integer.parseInt(commands[1]);
        try {
            List<Integer> videoIds = network.queryReceivedUnwatchedVideos(userId);
            System.out.println("query_received_unwatched_videos succeeded");
            if (videoIds.isEmpty()) {
                System.out.println("None");
            } else {
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < videoIds.size(); i++) {
                    sb.append(videoIds.get(i));
                    if (i < videoIds.size() - 1) {
                        sb.append(" ");
                    }
                }
                System.out.println(sb);
            }
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void queryUpFollowersAgeRatio() {
        int upId = Integer.parseInt(commands[1]);
        try {
            double[] ratios = network.queryUpFollowersAgeRatio(upId);
            String name = network.getUser(upId).getName();
            
            System.out.println("query_up_followers_age_ratio succeeded");
            System.out.printf("%s %.2f %.2f %.2f %.2f\n",
                    name, ratios[0], ratios[1], ratios[2], ratios[3]);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void queryMutualFollowingSum() {
        System.out.println(network.queryMutualFollowingSum());
    }
    
    private void queryShortestPath() {
        int id1 = Integer.parseInt(commands[1]);
        int id2 = Integer.parseInt(commands[2]);
        try {
            System.out.println(network.queryShortestPath(id1, id2));
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (UncessException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void addUserCoins() {
        int userId = Integer.parseInt(commands[1]);
        int coins = Integer.parseInt(commands[2]);
        try {
            network.addUserCoins(userId, coins);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void likeVideo() {
        int userId = Integer.parseInt(commands[1]);
        int videoId = Integer.parseInt(commands[2]);
        try {
            network.likeVideo(userId, videoId);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoUnwatchedException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (EqualUserIdException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void coinVideo() {
        int userId = Integer.parseInt(commands[1]);
        int videoId = Integer.parseInt(commands[2]);
        int amount = Integer.parseInt(commands[3]);
        try {
            network.coinVideo(userId, videoId, amount);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoUnwatchedException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (InvalidCoinsException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch(InsufficientCoinsException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (EqualUserIdException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void queryBestContributor() {
        int userId = Integer.parseInt(commands[1]);
        try {
            int id = network.queryBestContributor(userId);
            System.out.println(userId + "'s best contributor is " + id);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (NoContributorsException e ) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void forwardVideo() {
        int userId = Integer.parseInt(commands[1]);
        int videoId = Integer.parseInt(commands[2]);
        int followerId = Integer.parseInt(commands[3]);
        try {
            network.forwardVideo(userId, videoId, followerId);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoUnwatchedException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (FollowLinkNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void sendComment() {
        int userId = Integer.parseInt(commands[1]);
        int videoId = Integer.parseInt(commands[2]);
        int commentId = Integer.parseInt(commands[3]);
        String comment = commands.length == 4 ? "" : commands[4];
        try {
            network.sendComment(userId, videoId, commentId, comment);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (EqualCommentIdException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (InvalidCommentException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void cleanSpamComments() {
        int videoId = Integer.parseInt(commands[1]);
        String keyword = commands.length == 2 ? "" : commands[2];
        try {
            int[] ans = network.cleanSpamComments(videoId, keyword);
            System.out.println(ans[0] + " comments have been cleaned.");
            System.out.println("The maximum count of the keyword found in removed comments is " + ans[1]);
        } catch (VideoIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void queryMostPopularVideo() {
        String type = commands[1];
        try {
            VideoInterface video = network.queryMostPopularVideo(type);
            if (video == null) {
                System.out.println("The most popular video of " + type + " is NULL.");
            } else {
                System.out.println(type + "'s most popular video is " + video.getId());
            }
        } catch (InvalidTypeException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void purchaseMedal() {
        int userId = Integer.parseInt(commands[1]);
        int videoId = Integer.parseInt(commands[2]);
        int amount = Integer.parseInt(commands[3]);
        try {
            network.purchaseMedal(userId, videoId, amount);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (InsufficientCoinsException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (DuplicateMedalException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (EqualUserIdException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    public void queryLongestDecSeq() {
        System.out.println(network.queryLongestDecSeq());
    }

}