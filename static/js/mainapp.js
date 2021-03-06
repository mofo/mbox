var app = angular.module('mainApp', ['ui.router' , 'ui.bootstrap' , 'ngResource'], function($interpolateProvider) {
    $interpolateProvider.startSymbol('{[{');
    $interpolateProvider.endSymbol('}]}');
  });

app.config(function($stateProvider, $urlRouterProvider) {

    $urlRouterProvider.otherwise('');

    $stateProvider.state('main', {
        url         : '',
        //templateUrl : '/templates/playlist'
        //redirectTo  : 'playlist',
        onEnter     : function ($state){
            $state.go ('playlist');
        }
        //controller  : 'mainCtrl'
    })
    .state('playlist', {
        url         : '/playlist',
        templateUrl : '/templates/playlist'
        //controller  : 'mainCtrl'
    })
    .state('search', {
        url         : '/search',
        templateUrl : '/templates/search'
        //controller  : 'prodController'
    })
    .state('productstationroot', {
        url         : '/product/:productId/station/:stationId',
        templateUrl : function($stateParams){
            return '/product/' + $stateParams.productId + '/station/' + $stateParams.stationId;
        },
        resolve:{
            productId: function($stateParams){
                return $stateParams.productId;
            },
            stationId: function($stateParams){
                return $stateParams.stationId;
            }
        },
        controller  : 'statController'
    })
});

app.factory('songList', function($http, $q){
    var d = $q.defer();
    $http.get('/DocumentsList').success(function(data){
        d.resolve(data);
    });
    return d.promise;
});

var serverAddress = 'http://localhost:5000';

app.controller('mainCtrl', ['$scope', '$resource', '$http', '$interval', '$state', function($scope, $resource, $http, $interval, $state) {

    $scope.playbuttongliph = 'glyphicon glyphicon-play'
    $scope.songs = [];

    var currentPlayingSong = '';
    var currentPlayingListLength = 0;
    var currentToken = 0;
    var newToken = 0;
    var isplaying = false;

    $scope.searchtext = function() {
        $state.go('search');
        var searchapi = '/api/search/text/' + $scope.searchstring;
        var NewIssue = $resource(searchapi);
        $scope.songs.length = 0;
        $scope.songs = NewIssue.query();
        $scope.songs.$promise.then(function(){
            $scope.totalItems = $scope.songs.length;
            //console.log($scope.totalItems);
        });
    };

    $scope.searchnextprev = function(value) {
        var searchapi = '/api/search/' + value;
        console.log(searchapi);
        var NewIssue = $resource(searchapi);
        $scope.songs.length = 0;
        $scope.songs = NewIssue.query();
        $scope.songs.$promise.then(function(){
            $scope.totalItems = $scope.songs.length;
            //console.log($scope.totalItems);
        });
    };

    $scope.addsong = function(songNum) {
        var addapi = '/api/playlist/add/' + songNum;
        //$http.post(addapi);
        $state.go('playlist');
        //$scope.playstatus();
        var NewIssue = $resource(addapi);
        $scope.songs.length = 0;

        var newPlaylist = NewIssue.get();
        newPlaylist.$promise.then(function(){
            $scope.songs = newPlaylist.songs
            $scope.totalItems = $scope.songs.length;
            currentToken = newPlaylist.header.pl_token;
            //console.log('addsong token: ' + currentToken);
        });
    };

    $scope.playctrl = function(command) {

        if (command == 'invert') {
            if (isplaying) {
                command = 'stop'
            } else {
                command = 'play'
            }
        }

        var searchapi = '/api/playctrl/' + command;
        $http.post(searchapi);
    };

    $scope.playstatus = function() {
        var searchapi = 'api/playstatus';
        var NewIssue = $resource(searchapi);
        var results = NewIssue.get();

        results.$promise.then(function(){
            $scope.statusPercent = Math.round(results.percentElapsed);
            $scope.statusNowPlaying = results.nowPlaying;
            newToken = results.pl_token;

            //console.log('new Token' + newToken);
            //console.log('currentToken Token' + currentToken);

            if (isplaying != results.isplaying) {
                isplaying = results.isplaying;
                if (results.isplaying) {
                    $scope.playbuttongliph = 'glyphicon glyphicon-stop'
                } else {
                    $scope.playbuttongliph = 'glyphicon glyphicon-play'
                }
            }

            if (newToken != currentToken) {

                currentToken = newToken;

                var Playlist = $resource('api/playlist/get');
                var newPlaylist = Playlist.get();
                //$scope.songs.length = 0;
                newPlaylist.$promise.then(function(){
                    //console.log('Test');

                    $scope.songs = newPlaylist.songs;
                    $scope.totalItems = $scope.songs.length;
                });
            }

        });
    };

    $scope.paginate = function(value) {
        var begin, end, index;
        begin = ($scope.currentPage - 1) * $scope.numPerPage;
        end = begin + $scope.numPerPage;
        index = $scope.songs.indexOf(value);
        return (begin <= index && index < end);
    };

    // update the play head
    $scope.playstatus();

    //console.log($scope.songs)

    $interval( function(){ $scope.playstatus(); }, 3000);
    //$scope.songs = []

}]);

app.controller('statController', function($scope, $http, $stateParams, $state) {
    $scope.init = function() {
        var buildsapi = 'http://localhost:5000/' + $stateParams.productId + '/' +$stateParams.stationId + '/buildsandtests';
        $http.get(buildsapi).then(
            function(response){
                $scope.builds = response.data;
                console.log($scope.builds)
                $scope.selectedBuild = $scope.builds[0];
                $scope.stationId = $stateParams.stationId;
                $scope.productId = $stateParams.productId;

                var testapi = 'http://localhost:5000/'+ $stateParams.productId +'/tests/' + $stateParams.stationId + '/build/' + $scope.selectedBuild;
                    $http.get(testapi).then(
                        function(response){
                            $scope.tests = response.data;
                            console.log($scope.tests)
                            $scope.selectedTest = $scope.tests[0];
                    } );
            })
    }
    $scope.selecttest = function(index) {
        $scope.selectedTest  = $scope.tests[index];
        $state.go("productstationroot.testid", {"buildid": $scope.selectedBuild, "testid": $scope.selectedTest})
    }
    $scope.selectbuild = function(index) {
        $scope.selectedBuild = $scope.builds[index];
        var testapi = 'http://localhost:5000/'+ $scope.productId +'/tests/' + $scope.stationId + '/build/' + $scope.selectedBuild;
            $http.get(testapi).then(
                function(response){
                    $scope.tests = response.data;
                    console.log($scope.tests)
                    $scope.selectedTest = $scope.tests[0];
            } );
    }
});

app.controller('corrController', function($scope, $http, $stateParams, $state) {
    $scope.init = function() {
        var buildsapi = 'http://localhost:5000/' + $stateParams.productId + '/corr/' +$stateParams.corrId + '/buildsandtests_corr';
        $http.get(buildsapi).then(
            function(response){
                $scope.builds = response.data;
                console.log($scope.builds)
                $scope.selectedBuild = $scope.builds[0];
                $scope.corrId = $stateParams.corrId;
                $scope.productId = $stateParams.productId;

                var testapi = 'http://localhost:5000/'+ $stateParams.productId +'/tests/corr/' + $stateParams.corrId + '/build/' + $scope.selectedBuild;
                    $http.get(testapi).then(
                        function(response){
                            $scope.tests = response.data;
                            console.log("hello")
                            console.log($scope.tests)
                            $scope.selectedTest = $scope.tests[0];
                    } );
            })
    }
    $scope.selecttest = function(index) {
        $scope.selectedTest  = $scope.tests[index];
        $state.go("productcorrroot.testid", {"buildid": $scope.selectedBuild, "testid": $scope.selectedTest})
    }
    $scope.selectbuild = function(index) {
        $scope.selectedBuild = $scope.builds[index];
        var testapi = 'http://localhost:5000/'+ $scope.productId +'/tests/corr' + $scope.corrId + '/build/' + $scope.selectedBuild;
            $http.get(testapi).then(
                function(response){
                    $scope.tests = response.data;
                    console.log($scope.tests)
                    $scope.selectedTest = $scope.tests[0];
            } );
    }
});